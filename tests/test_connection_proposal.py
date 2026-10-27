import pytest
from fastapi.testclient import TestClient

from aura.workspace.server import create_app


@pytest.fixture()
def fan(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        project = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()
        yield client, project["projectId"]


def connect(client, project_id, source, source_interface, target, target_interface, base=1):
    return client.post(f"/api/projects/{project_id}/connection-proposals", json={"baseRevision": base, "sourceId": source, "sourceInterface": source_interface,
                                                                                 "targetId": target, "targetInterface": target_interface})


def test_compatible_pair_proposes_an_attachment_that_commits(fan):
    client, project_id = fan
    response = connect(client, project_id, "component-support", "mount-face-3", "component-pull-up", "body-mount")
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["mode"] == "connection"
    assert proposal["operations"][0]["operation"] in {"add_mechanical_attachment", "update_mechanical_attachment"}
    assert proposal["operations"][0]["newValue"]["sourceInterface"] == "mount-face-3"
    assert client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit").status_code == 200


def test_incompatible_occupied_unknown_and_stale_are_rejected(fan):
    client, project_id = fan
    bad = connect(client, project_id, "component-support", "mount-face-3", "component-fan", "power")
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "incompatible_attachment_interfaces"
    used = connect(client, project_id, "component-support", "mount-face", "component-pull-up", "body-mount")
    assert used.status_code == 422 and used.json()["detail"]["code"] == "attachment_interface_in_use"
    missing = connect(client, project_id, "component-support", "mount-face-3", "component-missing", "body-mount")
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "UNKNOWN_COMPONENT"
    stale = connect(client, project_id, "component-support", "mount-face-3", "component-pull-up", "body-mount", base=0)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_revision"


def test_interfaces_route_lists_names_kinds_and_compatibility(fan):
    client, project_id = fan
    response = client.get(f"/api/projects/{project_id}/components/component-support/interfaces")
    assert response.status_code == 200, response.text
    faces = {item["name"]: item for item in response.json()}
    assert faces["mount-face-3"] == {"name": "mount-face-3", "kind": "structural_face", "compatible": ["fixed_mount"]}
    assert client.get(f"/api/projects/{project_id}/components/component-missing/interfaces").status_code == 404
