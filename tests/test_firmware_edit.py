import pytest
from fastapi.testclient import TestClient

from aura.firmware.compile import find_cli
from aura.firmware.sketch import extract_control, splice_control
from aura.workspace.server import create_app

EDITED = """bool fanControl(bool prevOn, float tC, bool valid, float tOn, float tOff) {
  if (!valid) return true;
  return tC >= tOn;  // edited: no hysteresis
}
"""


@pytest.fixture()
def fan(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        project = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()
        yield client, project["projectId"]


def test_splice_replaces_only_block(fan):
    client, project_id = fan
    source = client.get(f"/api/projects/{project_id}/firmware").json()["source"]
    spliced = splice_control(source, EDITED)
    assert extract_control(spliced) == EDITED
    assert spliced.replace(EDITED, "") == source.replace(extract_control(source), "")


def test_edit_must_keep_signature(fan):
    client, project_id = fan
    revision = client.get(f"/api/projects/{project_id}/firmware").json()["revisionId"]
    response = client.put(f"/api/projects/{project_id}/firmware/edit", json={"block": "void loop() {}", "revisionId": revision})
    assert response.status_code == 422 and response.json()["detail"]["code"] == "CONTROL_SIGNATURE_REQUIRED"


def test_edit_saved_shown_and_reset(fan):
    client, project_id = fan
    generated = client.get(f"/api/projects/{project_id}/firmware").json()
    assert generated["edit"] is None and generated["controlBlock"] == extract_control(generated["source"])
    saved = client.put(f"/api/projects/{project_id}/firmware/edit", json={"block": EDITED, "revisionId": generated["revisionId"]})
    assert saved.status_code == 200, saved.text
    edited = client.get(f"/api/projects/{project_id}/firmware").json()
    assert edited["edit"] == {"revisionId": generated["revisionId"], "needsReview": False}
    assert "edited: no hysteresis" in edited["source"] and edited["pins"] == generated["pins"]
    assert client.delete(f"/api/projects/{project_id}/firmware/edit").status_code == 204
    assert client.get(f"/api/projects/{project_id}/firmware").json()["source"] == generated["source"]


def test_edit_on_stale_revision_rejected(fan):
    client, project_id = fan
    response = client.put(f"/api/projects/{project_id}/firmware/edit", json={"block": EDITED, "revisionId": "revision-old"})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "stale_revision"


def test_edit_flagged_after_revision_change(fan):
    client, project_id = fan
    revision = client.get(f"/api/projects/{project_id}/firmware").json()["revisionId"]
    client.put(f"/api/projects/{project_id}/firmware/edit", json={"block": EDITED, "revisionId": revision})
    proposal = client.post(f"/api/projects/{project_id}/pin-proposals", json={"baseRevision": 1, "controllerId": "component-controller", "port": "signal-2", "gpio": 17}).json()
    assert client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit").status_code == 200
    after = client.get(f"/api/projects/{project_id}/firmware").json()
    assert after["edit"]["needsReview"] is True
    assert after["pins"]["fan_gate"] == 17 and "edited: no hysteresis" in after["source"]


@pytest.mark.skipif(find_cli() is None, reason="arduino-cli not installed; set AURA_ARDUINO_CLI")
def test_compile_uses_edit_and_reports_bad_edits(fan):
    client, project_id = fan
    revision = client.get(f"/api/projects/{project_id}/firmware").json()["revisionId"]
    client.put(f"/api/projects/{project_id}/firmware/edit", json={"block": EDITED, "revisionId": revision})
    assert client.post(f"/api/projects/{project_id}/firmware/compile").json()["status"] == "passed"
    broken = EDITED.replace("return tC >= tOn;", "return tC >= undefinedThing;")
    client.put(f"/api/projects/{project_id}/firmware/edit", json={"block": broken, "revisionId": revision})
    result = client.post(f"/api/projects/{project_id}/firmware/compile").json()
    assert result["status"] == "failed" and result["errors"]
