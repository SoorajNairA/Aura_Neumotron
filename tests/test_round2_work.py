from fastapi.testclient import TestClient
from aura.workspace.server import create_app

OBJECTIVE="Design a low voltage robotic arm with servo actuators and a controller"

def project(client):
    response=client.post("/api/projects",json={"objective":OBJECTIVE,"planningMode":"deterministic_test"}); assert response.status_code==201,response.text
    return response.json()["projectId"]

def test_work_transitions_reasons_history_and_reopen(tmp_path):
    db=tmp_path/"aura.db"; artifacts=tmp_path/"artifacts"; app=create_app(storage_mode="sqlite",db_path=db,artifact_dir=artifacts)
    with TestClient(app) as client:
        pid=project(client); created=client.post(f"/api/projects/{pid}/work",json={"title":"Verify actuator capability"}).json(); wid=created["id"]
        assert client.post(f"/api/projects/{pid}/work/{wid}/transition",json={"targetState":"IN_PROGRESS"}).status_code==200
        missing=client.post(f"/api/projects/{pid}/work/{wid}/transition",json={"targetState":"PAUSED","reason":"   "})
        assert missing.status_code==422 and missing.json()["detail"]["code"]=="WORK_REASON_REQUIRED"
        paused=client.post(f"/api/projects/{pid}/work/{wid}/transition",json={"targetState":"PAUSED","reason":"Waiting for verified panel mass."}).json()
        assert paused["state"]=="PAUSED" and paused["currentReason"]=="Waiting for verified panel mass."
    app.state.workspace.repository.close()
    reopened=create_app(storage_mode="sqlite",db_path=db,artifact_dir=artifacts)
    with TestClient(reopened) as client:
        item=client.get(f"/api/projects/{pid}/work").json()["items"][0]
        assert item["state"]=="PAUSED" and len(item["transitionHistory"])==2

def test_terminal_invalid_and_project_isolation():
    app=create_app(storage_mode="memory")
    with TestClient(app) as client:
        first=project(client); item=client.post(f"/api/projects/{first}/work",json={"title":"Electrical architecture"}).json()
        client.post(f"/api/projects/{first}/work/{item['id']}/transition",json={"targetState":"IN_PROGRESS"})
        client.post(f"/api/projects/{first}/work/{item['id']}/transition",json={"targetState":"COMPLETED"})
        invalid=client.post(f"/api/projects/{first}/work/{item['id']}/transition",json={"targetState":"PAUSED","reason":"No"})
        assert invalid.status_code==422 and invalid.json()["detail"]["code"]=="WORK_TRANSITION_INVALID"
        second=client.post("/api/projects",json={"objective":"Design a low voltage temperature monitor with sensor and display","planningMode":"deterministic_test"}).json()["projectId"]
        assert client.get(f"/api/projects/{second}/work").json()["items"]==[]
        assert client.post(f"/api/projects/{second}/work/{item['id']}/transition",json={"targetState":"PAUSED","reason":"x"}).status_code==404

def test_skip_abandon_and_natural_language_use_same_rules():
    app=create_app(storage_mode="memory")
    with TestClient(app) as client:
        pid=project(client); enclosure=client.post(f"/api/projects/{pid}/work",json={"title":"Enclosure work"}).json()
        no_reason=client.post(f"/api/projects/{pid}/work/command",json={"command":"Skip the enclosure work"})
        assert no_reason.status_code==422 and no_reason.json()["detail"]["code"]=="WORK_REASON_REQUIRED"
        skipped=client.post(f"/api/projects/{pid}/work/command",json={"command":"Skip the enclosure work because outside current prototype scope."}).json()
        assert skipped["state"]=="SKIPPED" and skipped["currentReason"]=="outside current prototype scope."
        other=client.post(f"/api/projects/{pid}/work",json={"title":"Verify power"}).json()
        client.post(f"/api/projects/{pid}/work/{other['id']}/transition",json={"targetState":"IN_PROGRESS"})
        abandoned=client.post(f"/api/projects/{pid}/work/{other['id']}/transition",json={"targetState":"ABANDONED","reason":"Replaced by verified module"})
        assert abandoned.status_code==200
