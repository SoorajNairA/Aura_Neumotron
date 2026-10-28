from __future__ import annotations

import io
import json
import zipfile

import keyring
import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.serialization import graph_to_dict
from aura.workspace.project_package import MAX_PACKAGE_BYTES, PackageError, read_zip
from aura.workspace.server import create_app
from tests.test_model_profiles import KEY, OPENAI, MemoryKeyring

FAN = "Build a temperature-controlled desk fan"
EDITED = """bool fanControl(bool prevOn, float tC, bool valid, float tOn, float tOff) {
  if (!valid) return true;
  return tC >= tOn;  // edited: no hysteresis
}
"""
LAYOUT = {"parts": {"component-controller": {"x": 12, "y": -4}}, "wires": {"wire-1": {"bends": [3]}}, "labels": {"component-controller": "Brain"}}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NEBIUS_API_KEY", KEY)
    previous = keyring.get_keyring()
    keyring.set_keyring(MemoryKeyring())
    app = create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")
    with TestClient(app) as client:
        client.application = app.state.workspace
        # A configured key must never leave through a project package.
        assert client.put("/api/model-profiles/work-openai", json={k: v for k, v in OPENAI.items() if k != "profileId"}).status_code == 200
        assert client.put("/api/model-profiles/work-openai/key", json={"key": KEY}).status_code == 204
        yield client
    keyring.set_keyring(previous)


@pytest.fixture
def fan(api):
    project = api.post("/api/projects", json={"objective": FAN, "planningMode": "deterministic_test"})
    assert project.status_code == 201, project.text
    project_id = project.json()["projectId"]
    revision = api.get(f"/api/projects/{project_id}/firmware").json()["revisionId"]
    assert api.put(f"/api/projects/{project_id}/firmware/edit", json={"block": EDITED, "revisionId": revision}).status_code == 200
    assert api.put(f"/api/projects/{project_id}/layout", json={"layout": LAYOUT}).status_code == 200
    api.application.repository.save_control_rules(project_id, {"rules": [], "source": "default", "explanation": "kept"})
    api.application.repository.save_hardware_evidence(project_id, {"port": "FAKE", "ok": True})
    return project_id


def zip_bytes(members: dict[str, bytes | str], compression=zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def good_members(api, project_id) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(api.get(f"/api/projects/{project_id}/export").content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def post_import(api, data: bytes):
    return api.post("/api/projects/import", content=data, headers={"Content-Type": "application/zip"})


def norm(value):
    return json.loads(json.dumps(value))


def renamed(value, old, new):
    return json.loads(json.dumps(value).replace(old, new))


def test_layout_round_trip_and_default(api):
    project_id = api.post("/api/projects", json={"objective": FAN, "planningMode": "deterministic_test"}).json()["projectId"]
    assert api.get(f"/api/projects/{project_id}/layout").json() == {"layout": {"parts": {}, "wires": {}, "labels": {}}, "updatedAt": None}
    response = api.put(f"/api/projects/{project_id}/layout", json={"layout": LAYOUT})
    assert response.status_code == 200 and response.json()["updatedAt"]
    saved = api.get(f"/api/projects/{project_id}/layout").json()
    assert saved["layout"] == LAYOUT and saved["updatedAt"] == response.json()["updatedAt"]
    empty = {"parts": {}, "wires": {}, "labels": {}}
    assert api.put(f"/api/projects/{project_id}/layout", json={"layout": empty}).status_code == 200
    assert api.get(f"/api/projects/{project_id}/layout").json()["layout"] == empty


def test_layout_unknown_project_and_bad_fields(api, fan):
    assert api.get("/api/projects/project-nope/layout").status_code == 404
    assert api.put("/api/projects/project-nope/layout", json={"layout": LAYOUT}).status_code == 404
    for bad in ({"layout": {"parts": [], "wires": {}, "labels": {}}}, {"layout": {"parts": {}, "wires": "x", "labels": {}}},
                {"layout": {"parts": {}, "wires": {}, "labels": 3}}, {"layout": []}, {"nope": 1}):
        assert api.put(f"/api/projects/{fan}/layout", json=bad).status_code == 422, bad
    assert api.get(f"/api/projects/{fan}/layout").json()["layout"] == LAYOUT


def test_export_contents_and_no_secrets(api, fan):
    response = api.get(f"/api/projects/{fan}/export")
    assert response.status_code == 200 and response.headers["content-type"].startswith("application/zip")
    assert response.headers["content-disposition"].startswith('attachment; filename="aura-') and response.headers["content-disposition"].endswith('.zip"')
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert {"manifest.json", "graph.json", "project.json", "layout.json", "firmware/main.ino"} <= names
        assert {"control-rules.json", "hardware-evidence.json", "firmware/edit.json"} <= names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format"] == "aura-project" and manifest["version"] == 1 and manifest["projectId"] == fan and manifest["objective"] == FAN
        assert "edited: no hysteresis" in archive.read("firmware/main.ino").decode()
    assert KEY.encode() not in response.content and b"api_key" not in response.content
    # Stored (uncompressed) member bytes are checked too, not only the compressed archive.
    for value in good_members(api, fan).values():
        assert KEY.encode() not in value and b"api_key" not in value
    assert api.get("/api/projects/project-nope/export").status_code == 404


def test_import_round_trip(api, fan):
    original = api.application.repository.get_project(fan)
    exported = api.get(f"/api/projects/{fan}/export").content
    response = post_import(api, exported)
    assert response.status_code == 201, response.text
    body = response.json()
    new_id = body["projectId"]
    assert new_id != fan and new_id.startswith("project-") and body["objective"] == FAN
    restored = api.application.repository.get_project(new_id)
    assert norm(graph_to_dict(restored.graph)) == renamed(graph_to_dict(original.graph), fan, new_id)
    assert restored.graph.project_id == new_id and restored.objective == original.objective
    assert api.get(f"/api/projects/{new_id}/layout").json()["layout"] == LAYOUT
    assert api.application.repository.get_control_rules(new_id) == {"rules": [], "source": "default", "explanation": "kept"}
    assert api.application.repository.get_hardware_evidence(new_id) == {"port": "FAKE", "ok": True}
    firmware = api.get(f"/api/projects/{new_id}/firmware").json()
    assert "edited: no hysteresis" in firmware["source"] and firmware["edit"] == {"revisionId": firmware["revisionId"], "needsReview": False}
    assert all(item["status"] == "ready" for item in body["representations"]) and body["representations"]
    assert api.get(f"/api/projects/{new_id}").status_code == 200 and api.get(f"/api/projects/{new_id}/graph").status_code == 200
    assert [p["projectId"] for p in api.get("/api/projects").json()].count(new_id) == 1
    events = [event.type for event in api.application.repository.get_events_after(new_id, 0)]
    assert "project.imported" in events
    imported = next(e for e in api.application.repository.get_events_after(new_id, 0) if e.type == "project.imported")
    assert imported.payload["origin"] == "imported" and imported.payload["sourceProjectId"] == fan
    # The source project is untouched.
    assert api.application.repository.get_project(fan).graph == original.graph
    # Importing twice gives two independent projects.
    assert post_import(api, exported).json()["projectId"] not in {fan, new_id}


def test_copy(api, fan):
    original = api.application.repository.get_project(fan)
    response = api.post(f"/api/projects/{fan}/copy")
    assert response.status_code == 201, response.text
    new_id = response.json()["projectId"]
    assert new_id != fan
    copied = api.application.repository.get_project(new_id)
    assert norm(graph_to_dict(copied.graph)) == renamed(graph_to_dict(original.graph), fan, new_id)
    assert api.get(f"/api/projects/{new_id}/layout").json()["layout"] == LAYOUT
    assert "edited: no hysteresis" in api.get(f"/api/projects/{new_id}/firmware").json()["source"]
    event = next(e for e in api.application.repository.get_events_after(new_id, 0) if e.type == "project.copied")
    assert event.payload["origin"] == "copied" and event.payload["sourceProjectId"] == fan
    # Layout of the copy is independent of the original.
    api.put(f"/api/projects/{new_id}/layout", json={"layout": {"parts": {}, "wires": {}, "labels": {}}})
    assert api.get(f"/api/projects/{fan}/layout").json()["layout"] == LAYOUT
    assert api.post("/api/projects/project-nope/copy").status_code == 404


MANIFEST = {"format": "aura-project", "version": 1, "exportedAt": "2026-10-29T00:00:00+00:00", "projectId": "project-x", "objective": "x" * 10, "appVersion": "0"}


def code_of(response) -> str:
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["message"]
    return detail["code"]


def test_bad_zips_each_code(api, fan):
    good = good_members(api, fan)
    before = len(api.get("/api/projects").json())

    def case(members):
        return code_of(post_import(api, zip_bytes(members)))

    assert code_of(post_import(api, b"this is not a zip")) == "NOT_A_ZIP"
    assert code_of(post_import(api, b"")) == "NOT_A_ZIP"
    assert case({"readme.txt": "hi"}) == "NOT_AN_AURA_PROJECT"
    assert case({"manifest.json": "{nope"}) == "NOT_AN_AURA_PROJECT"
    assert case({"manifest.json": json.dumps(MANIFEST | {"format": "other"})}) == "NOT_AN_AURA_PROJECT"
    assert case({"manifest.json": json.dumps([1, 2])}) == "NOT_AN_AURA_PROJECT"
    assert case(good | {"manifest.json": json.dumps(MANIFEST | {"version": 2})}) == "UNSUPPORTED_VERSION"
    assert case(good | {"manifest.json": json.dumps(MANIFEST | {"version": "1"})}) == "UNSUPPORTED_VERSION"
    for name in ("../evil.txt", "/etc/passwd", "firmware\\other.ino", "..\\evil.txt", "C:/x.txt", "extra.txt", "artifacts/x.bin", "firmware/../graph.json", "firmware/"):
        assert case(good | {name: "x"}) == "UNSAFE_PATH", name
    dup = io.BytesIO()
    with zipfile.ZipFile(dup, "w") as archive:
        for name, value in good.items(): archive.writestr(name, value)
        with pytest.warns(UserWarning): archive.writestr("layout.json", b"{}")
    assert code_of(post_import(api, dup.getvalue())) == "UNSAFE_PATH"
    assert case(good | {"graph.json": "{not json"}) == "CORRUPT_GRAPH"
    assert case(good | {"graph.json": "[]"}) == "CORRUPT_GRAPH"
    graph = json.loads(good["graph.json"])
    assert case(good | {"graph.json": json.dumps(graph | {"entities": graph["entities"] + [graph["entities"][0]]})}) == "CORRUPT_GRAPH"
    assert case(good | {"graph.json": json.dumps(graph | {"project_id": "project-missing"})}) == "CORRUPT_GRAPH"
    assert case(good | {"graph.json": json.dumps(graph | {"revisions": []})}) == "CORRUPT_GRAPH"
    assert case({k: v for k, v in good.items() if k != "graph.json"}) == "CORRUPT_GRAPH"
    assert case(good | {"graph.json": json.dumps(graph | {"schema_version": "9.9"})}) == "CORRUPT_GRAPH"
    assert case(good | {"layout.json": json.dumps({"parts": []})}) == "CORRUPT_GRAPH"
    assert case(good | {"project.json": "[]"}) == "CORRUPT_GRAPH"
    assert case(good | {"firmware/edit.json": json.dumps({"block": 3})}) == "CORRUPT_GRAPH"
    assert len(api.get("/api/projects").json()) == before, "a rejected import must write nothing"


def test_too_large_body_and_zip_bomb(api, fan):
    before = len(api.get("/api/projects").json())
    too_big = b"0" * (MAX_PACKAGE_BYTES + 1024 * 1024)
    assert code_of(post_import(api, too_big)) == "TOO_LARGE"
    chunks = (too_big[i:i + 1024 * 1024] for i in range(0, len(too_big), 1024 * 1024))
    assert code_of(api.post("/api/projects/import", content=chunks, headers={"Content-Type": "application/zip"})) == "TOO_LARGE"
    good = good_members(api, fan)
    bomb = zip_bytes(good | {"layout.json": b" " * (MAX_PACKAGE_BYTES + 1)})
    assert len(bomb) < 1024 * 1024
    assert code_of(post_import(api, bomb)) == "TOO_LARGE"
    two = zip_bytes(good | {"layout.json": b" " * (MAX_PACKAGE_BYTES // 2 + 10), "control-rules.json": b" " * (MAX_PACKAGE_BYTES // 2 + 10)})
    assert code_of(post_import(api, two)) == "TOO_LARGE"
    assert len(api.get("/api/projects").json()) == before


def test_read_zip_is_pure_validation():
    with pytest.raises(PackageError) as caught:
        read_zip(b"nope")
    assert caught.value.code == "NOT_A_ZIP"


def test_path_rules_reject_backslash_and_traversal_directly():
    from aura.workspace.project_package import _unsafe
    for name in ("firmware" + chr(92) + "main.ino", ".." + chr(92) + "x", "../x", "/abs", "firmware//main.ino", "./graph.json", "C:graph.json", "unknown.txt"):
        assert _unsafe(name), name
    assert not _unsafe("firmware/main.ino") and not _unsafe("manifest.json")
