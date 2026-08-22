from fastapi.testclient import TestClient
from aura.workspace.server import create_app

OBJECTIVE="Design a low voltage robotic arm with servo actuators and a controller"

def setup(client):
    p=client.post("/api/projects",json={"objective":OBJECTIVE,"planningMode":"deterministic_test"}).json();g=client.get(f"/api/projects/{p['projectId']}/graph").json()
    component=next(x for x in g["entities"] if x["kind"]=="component" and x["metadata"].get("family")=="servo")
    return p,component

def test_candidate_isolated_discard_and_apply_revision():
    app=create_app(storage_mode="memory")
    with TestClient(app) as client:
        project,component=setup(client);pid=project["projectId"];base=project["revision"]
        scenario=client.post(f"/api/projects/{pid}/scenarios",json={"targetSemanticId":component["id"],"changeType":"REPLACE_COMPONENT","value":{"name":"SG90 Micro Servo","componentDefinitionId":"sg90"}})
        assert scenario.status_code==200,scenario.text; data=scenario.json();assert data["analysis"]["candidate"]["component"]["name"]=="SG90 Micro Servo"
        assert next(x for x in client.get(f"/api/projects/{pid}/graph").json()["entities"] if x["id"]==component["id"])["name"]==component["name"]
        assert "confidence" in data["analysis"] and not isinstance(data["analysis"]["confidence"],(int,float))
        client.delete(f"/api/projects/{pid}/scenarios/{data['scenarioId']}")
        assert client.get(f"/api/projects/{pid}").json()["revision"]==base
        again=client.post(f"/api/projects/{pid}/scenarios",json={"targetSemanticId":component["id"],"changeType":"REPLACE_COMPONENT","value":{"name":"SG90 Micro Servo"}}).json()
        applied=client.post(f"/api/projects/{pid}/scenarios/{again['scenarioId']}/apply")
        assert applied.status_code==200,applied.text;assert applied.json()["revision"]==base+1
        assert next(x for x in client.get(f"/api/projects/{pid}/graph").json()["entities"] if x["id"]==component["id"])["name"]=="SG90 Micro Servo"

def test_scenario_work_and_stale_protection():
    app=create_app(storage_mode="memory")
    with TestClient(app) as client:
        project,component=setup(client);pid=project["projectId"]
        first=client.post(f"/api/projects/{pid}/scenarios",json={"targetSemanticId":component["id"],"changeType":"REPLACE_COMPONENT","value":{"name":"SG90 Micro Servo"}}).json()
        work=client.post(f"/api/projects/{pid}/scenarios/{first['scenarioId']}/work")
        assert work.status_code==201 and work.json()["relatedComponentIds"]==[component["id"]]
        # A normal committed modification makes the ephemeral base stale.
        proposal=client.post(f"/api/projects/{pid}/modification-proposals",json={"projectId":pid,"baseRevision":project["revision"],"selectedSemanticIds":[component["id"]],"request":"replace with SG90","mode":"automatic"})
        if proposal.status_code==200:
            client.post(f"/api/projects/{pid}/modification-proposals/{proposal.json()['proposalId']}/commit")
            stale=client.post(f"/api/projects/{pid}/scenarios/{first['scenarioId']}/apply")
            assert stale.status_code==409 and stale.json()["detail"]["code"]=="SCENARIO_STALE"
