import pytest
from fastapi.testclient import TestClient

from aura.workspace.server import create_app


@pytest.fixture()
def fan(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        project = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()
        yield client, project["projectId"]


def propose(client, project_id, gpio, port="signal-2", base=1):
    return client.post(f"/api/projects/{project_id}/pin-proposals",
                       json={"baseRevision": base, "controllerId": "component-controller", "port": port, "gpio": gpio})


def commit(client, project_id, proposal):
    return client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit")


def test_pin_change_commit_updates_firmware_pins(fan):
    client, project_id = fan
    before = client.get(f"/api/projects/{project_id}/firmware").json()
    assert before["pins"]["fan_gate"] == 16
    proposal = propose(client, project_id, 17)
    assert proposal.status_code == 200, proposal.text
    assert proposal.json()["operations"][0]["newValue"] == 17
    response = commit(client, project_id, proposal.json())
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    after = client.get(f"/api/projects/{project_id}/firmware").json()
    assert after["pins"]["fan_gate"] == 17 and after["pins"]["temperature_data"] == 4
    assert after["revisionId"] != before["revisionId"]
    assert "17" in after["source"]


def test_undo_restores_pin(fan):
    client, project_id = fan
    commit(client, project_id, propose(client, project_id, 17).json())
    undo = client.post(f"/api/projects/{project_id}/revisions/undo", headers={"Idempotency-Key": "undo-1"})
    assert undo.status_code == 200, undo.text
    assert client.get(f"/api/projects/{project_id}/firmware").json()["pins"]["fan_gate"] == 16


def test_duplicate_gpio_rejected_by_verification(fan):
    client, project_id = fan
    proposal = propose(client, project_id, 4)
    assert proposal.status_code == 200, proposal.text
    response = commit(client, project_id, proposal.json())
    assert response.status_code == 422 and response.json()["detail"]["code"] == "verification_rejected"
    assert client.get(f"/api/projects/{project_id}/firmware").json()["pins"]["fan_gate"] == 16


@pytest.mark.parametrize("gpio", [34, 5, 6, 99])
def test_input_only_strapping_or_unknown_rejected(fan, gpio):
    client, project_id = fan
    response = propose(client, project_id, gpio)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "PIN_NOT_ALLOWED"


def test_unknown_port_rejected(fan):
    client, project_id = fan
    response = propose(client, project_id, 17, port="vcc-out")
    assert response.status_code == 422 and response.json()["detail"]["code"] == "UNKNOWN_PORT"


def test_stale_base_409(fan):
    client, project_id = fan
    commit(client, project_id, propose(client, project_id, 17).json())
    assert propose(client, project_id, 18, base=1).status_code == 409
