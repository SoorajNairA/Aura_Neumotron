import pytest
from fastapi.testclient import TestClient

from aura.workspace.server import create_app


@pytest.fixture()
def fan(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        project = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"}).json()
        yield client, project["projectId"]


def propose(client, project_id, key, value, component="component-temperature-sensor", base=1):
    return client.post(f"/api/projects/{project_id}/parameter-proposals",
                       json={"baseRevision": base, "componentId": component, "key": key, "value": value})


def test_scalar_change_is_a_replace_parameter_proposal_that_commits(fan):
    client, project_id = fan
    response = propose(client, project_id, "threshold_c", 30.0)
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["mode"] == "parameter_change"
    assert proposal["operations"][0]["operation"] == "replace_parameter"
    assert proposal["operations"][0]["path"] == "parameters.threshold_c" and proposal["operations"][0]["newValue"] == 30.0
    assert client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit").status_code == 200
    assert client.get(f"/api/projects/{project_id}/firmware").json()["tOnC"] == 30.0


def test_invalid_edits_are_rejected(fan):
    client, project_id = fan
    current = next(e for e in client.get(f"/api/projects/{project_id}/graph").json()["entities"] if e["id"] == "component-temperature-sensor")
    same = propose(client, project_id, "threshold_c", current["metadata"]["parameters"]["threshold_c"])
    assert same.status_code == 422 and same.json()["detail"]["code"] == "invalid_parameter_edit"
    assert propose(client, project_id, "no_such_key", 1).json()["detail"]["code"] == "PARAMETER_NOT_CONFIGURABLE"
    missing = propose(client, project_id, "threshold_c", 30.0, component="component-missing")
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "UNKNOWN_COMPONENT"
    stale = propose(client, project_id, "threshold_c", 30.0, base=0)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_revision"


@pytest.mark.parametrize("component,key,value", [
    ("component-driver", "max_current_a", 100),
    ("component-fan", "current_a", 50),
    ("component-temperature-sensor", "component_definition_id", "made-up-part"),
    ("component-driver", "flyback_protection", True),
])
def test_ratings_identity_and_safety_claims_are_not_configurable(fan, component, key, value):
    client, project_id = fan
    response = propose(client, project_id, key, value, component=component)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "PARAMETER_NOT_CONFIGURABLE"


@pytest.mark.parametrize("value", ["hot", 500, -80, True])
def test_threshold_must_be_a_number_in_the_sensor_range(fan, value):
    client, project_id = fan
    response = propose(client, project_id, "threshold_c", value)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "invalid_parameter_edit"
