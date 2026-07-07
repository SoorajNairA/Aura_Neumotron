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

def test_commit_regenerates_updates_assembly_survives_restart_and_undoes(tmp_path):
 db=tmp_path/"db";artifacts=tmp_path/"a";app=create_app(storage_mode="sqlite",db_path=db,artifact_dir=artifacts)
 with TestClient(app) as c:
  p=create(c);before=c.get(f'/api/projects/{p["projectId"]}/assembly').json();r=proposal(c,p,"component-reservoir","Increase capacity by 40% but keep height").json()
  out=c.post(f'/api/projects/{p["projectId"]}/modification-proposals/{r["proposalId"]}/commit').json();assert out["revision"]==2
  after=c.get(f'/api/projects/{p["projectId"]}/assembly').json();bp=next(x for x in before["parts"] if x["semanticId"]=="component-reservoir");ap=next(x for x in after["parts"] if x["semanticId"]=="component-reservoir")
  assert ap["dimensions"][:2]!=bp["dimensions"][:2] and ap["dimensions"][2]==bp["dimensions"][2]
  changed={x["representationId"]:x for x in out["representations"]};assert changed["repr-reservoir-3d"]["status"]=="ready" and changed["repr-tubing-3d"]["status"]=="ready"
 app.state.workspace.repository.close();app=create_app(storage_mode="sqlite",db_path=db,artifact_dir=artifacts)
 with TestClient(app) as c:
  assert c.get(f'/api/projects/{p["projectId"]}/assembly').json()==after
  revisions=c.get(f'/api/projects/{p["projectId"]}/revisions').json();assert revisions[-1]["verification"]["diff"]["affected"]==["component-reservoir","component-tubing"]
  undo=c.post(f'/api/projects/{p["projectId"]}/revisions/undo').json();assert undo["revision"]==3
  restored=c.get(f'/api/projects/{p["projectId"]}/assembly').json();rp=next(x for x in restored["parts"] if x["semanticId"]=="component-reservoir");assert rp["dimensions"]==bp["dimensions"]

def test_pump_and_driver_commits_regenerate_only_their_artifacts(tmp_path):
 app=create_app(storage_mode="sqlite",db_path=tmp_path/"db",artifact_dir=tmp_path/"a")
 with TestClient(app) as c:
  p=create(c);initial=c.get(f'/api/projects/{p["projectId"]}').json();ids={x["representationId"]:x.get("artifactId") for x in initial["representations"]}
  q=proposal(c,p,"component-pump","Move pump farther away and keep tubing connected").json();moved=c.post(f'/api/projects/{p["projectId"]}/modification-proposals/{q["proposalId"]}/commit').json();now={x["representationId"]:x.get("artifactId") for x in moved["representations"]};assert now["repr-tubing-3d"]!=ids["repr-tubing-3d"] and now["repr-reservoir-3d"]==ids["repr-reservoir-3d"]
  current=c.get(f'/api/projects/{p["projectId"]}').json();d=proposal(c,current,"component-driver","Replace this driver with a logic-level MOSFET suitable for pump").json();driver=c.post(f'/api/projects/{p["projectId"]}/modification-proposals/{d["proposalId"]}/commit').json();latest={x["representationId"]:x.get("artifactId") for x in driver["representations"]};assert latest["repr-irrigation-schematic"]!=now["repr-irrigation-schematic"] and latest["repr-tubing-3d"]==now["repr-tubing-3d"]
