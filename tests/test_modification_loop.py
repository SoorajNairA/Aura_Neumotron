from fastapi.testclient import TestClient
from aura.workspace.server import create_app

OBJECTIVE="Design a small ESP32 irrigation controller with pump, sensor, driver, tubing, reservoir, enclosure, and power."
def create(client):return client.post("/api/projects",json={"objective":OBJECTIVE,"planningMode":"deterministic_test"}).json()
def proposal(client,p,id,text,mode="automatic"):return client.post(f'/api/projects/{p["projectId"]}/modification-proposals',json={"projectId":p["projectId"],"baseRevision":p["revision"],"selectedSemanticIds":[id],"request":text,"mode":mode})

def test_preview_cancel_and_stale_revision(tmp_path):
 app=create_app(storage_mode="sqlite",db_path=tmp_path/"db",artifact_dir=tmp_path/"a")
 with TestClient(app) as c:
  p=create(c);r=proposal(c,p,"component-reservoir","Increase capacity by 40% but keep height")
  assert r.status_code==201 and set(r.json()["artifactsToRegenerate"])=={"repr-reservoir-3d","repr-tubing-3d"}
  assert c.delete(f'/api/projects/{p["projectId"]}/modification-proposals/{r.json()["proposalId"]}').json()["cancelled"]
  assert c.get(f'/api/projects/{p["projectId"]}').json()["revision"]==p["revision"]
  bad={"projectId":p["projectId"],"baseRevision":0,"selectedSemanticIds":["component-pump"],"request":"Move pump farther away"}
  assert c.post(f'/api/projects/{p["projectId"]}/modification-proposals',json=bad).status_code==409

def test_three_benchmark_proposals_are_selective_and_commit_persists(tmp_path):
 app=create_app(storage_mode="sqlite",db_path=tmp_path/"db",artifact_dir=tmp_path/"a")
 with TestClient(app) as c:
  p=create(c)
  r=proposal(c,p,"component-reservoir","Increase capacity by 40% but keep height","parameter_change").json()
  out=c.post(f'/api/projects/{p["projectId"]}/modification-proposals/{r["proposalId"]}/commit').json();assert out["revision"]==2 and "repr-irrigation-schematic" not in out["diff"]["regenerated"]
  p=c.get(f'/api/projects/{p["projectId"]}').json();q=proposal(c,p,"component-pump","Move pump farther away and keep tubing connected","position_change").json();assert q["artifactsToRegenerate"]==["repr-tubing-3d"]
  c.delete(f'/api/projects/{p["projectId"]}/modification-proposals/{q["proposalId"]}')
  d=proposal(c,p,"component-driver","Replace this driver with a logic-level MOSFET suitable for pump","component_replacement").json();assert d["artifactsToRegenerate"]==["repr-irrigation-schematic"]
 app.state.workspace.repository.close()
