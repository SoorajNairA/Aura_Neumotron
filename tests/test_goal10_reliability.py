import asyncio
from dataclasses import replace

from fastapi.testclient import TestClient

from aura.workspace.representations import RepresentationRecord, RepresentationStatus
from aura.infrastructure.persistence.project_repository import StoredEvent
from aura.workspace.server import CreateProjectBody, EventBroker, _remember_bounded, create_app


OBJECTIVE = "Design a small ESP32 irrigation controller with pump, sensor, driver, tubing, reservoir, enclosure, and low voltage power."


def create(client, operation="create-1"):
    response=client.post("/api/projects",json={"objective":OBJECTIVE,"planningMode":"deterministic_test","operationId":operation})
    assert response.status_code==201,response.text
    return response.json()


def propose(client, project, operation="proposal-1"):
    graph=client.get(f'/api/projects/{project["projectId"]}/graph').json()
    target=next(entity["id"] for entity in graph["entities"] if dict(entity["metadata"]).get("family") in {"container","reservoir"})
    response=client.post(f'/api/projects/{project["projectId"]}/modification-proposals',json={"projectId":project["projectId"],"baseRevision":project["revision"],"selectedSemanticIds":[target],"request":"Increase capacity by 40% but keep height","mode":"parameter_change","operationId":operation})
    assert response.status_code==201,response.text
    return response.json()


def test_writes_are_idempotent_and_durable_across_restart(tmp_path):
    db=tmp_path/"aura.db"; artifacts=tmp_path/"artifacts"
    app=create_app(storage_mode="sqlite",db_path=db,artifact_dir=artifacts)
    with TestClient(app) as client:
        first=create(client); second=create(client)
        assert first["projectId"]==second["projectId"] and second["revision"]==1
        proposal=propose(client,first); assert propose(client,first)["proposalId"]==proposal["proposalId"]
        url=f'/api/projects/{first["projectId"]}/modification-proposals/{proposal["proposalId"]}/commit'
        one=client.post(url,headers={"Idempotency-Key":"apply-1"}).json()
        two=client.post(url,headers={"Idempotency-Key":"apply-1"}).json()
        assert one==two and one["revision"]==2
        undo_url=f'/api/projects/{first["projectId"]}/revisions/undo'
        undone=client.post(undo_url,headers={"Idempotency-Key":"undo-1"}).json()
        repeated=client.post(undo_url,headers={"Idempotency-Key":"undo-1"}).json()
        assert undone==repeated and undone["revision"]==3
    app.state.workspace.repository.close()
    app=create_app(storage_mode="sqlite",db_path=db,artifact_dir=artifacts)
    with TestClient(app) as client:
        replayed=client.post(url,headers={"Idempotency-Key":"apply-1"}).json()
        # The original operation fields are durable; its proof is stale after undo.
        assert {key:value for key,value in replayed.items() if key!="assessment"}=={key:value for key,value in one.items() if key!="assessment"}
        assert replayed["assessment"]["freshness"]=="STALE"
        assert replayed["assessment"]["revisionNumber"]==one["revision"]==2
        assert replayed["assessment"]["assessedRevisionId"]==one["assessment"]["assessedRevisionId"]
        assert client.get(f'/api/projects/{first["projectId"]}').json()["revision"]==3


def test_idempotency_lookup_does_not_load_every_project_graph(tmp_path):
    app=create_app(storage_mode="sqlite",db_path=tmp_path/"aura.db",artifact_dir=tmp_path/"artifacts")
    with TestClient(app) as client:
        first=create(client,operation="indexed-create")

        def fail_if_scanned():
            raise AssertionError("idempotency lookup scanned all projects")

        app.state.workspace.repository.list_projects=fail_if_scanned
        repeated=create(client,operation="indexed-create")

        assert repeated["projectId"]==first["projectId"]


def test_stale_representation_callbacks_are_ignored(tmp_path):
    app=create_app(storage_mode="sqlite",db_path=tmp_path/"db",artifact_dir=tmp_path/"a")
    with TestClient(app) as client:
        project=create(client)
        record=next(x for x in project["representations"] if x["type"]=="mechanical_3d")
        url=f'/api/projects/{project["projectId"]}/representations/{record["representationId"]}/status'
        base={"status":"generating","projectId":project["projectId"],"revision":record["revision"],"operationId":record["operationId"],"generation":record["generation"]}
        assert client.post(url,json={**base,"projectId":"another-project"}).json()["ignored"]
        assert client.post(url,json={**base,"revision":record["revision"]+1}).json()["ignored"]
        assert client.post(url,json={**base,"operationId":"old-operation"}).json()["ignored"]
        assert client.post(url,json={**base,"generation":record["generation"]-1}).json()["ignored"]
        current=client.get(f'/api/projects/{project["projectId"]}').json()
        unchanged=next(x for x in current["representations"] if x["representationId"]==record["representationId"])
        assert unchanged["status"]==record["status"]


def test_interrupted_generation_recovers_to_visible_fallback(tmp_path):
    app=create_app(storage_mode="sqlite",db_path=tmp_path/"db",artifact_dir=tmp_path/"a")
    with TestClient(app) as client:
        project=create(client)
        workspace=app.state.workspace; stored=workspace.repository.get_project(project["projectId"])
        item=RepresentationRecord.from_dict(stored.representations[1])
        stuck=replace(item,status=RepresentationStatus.GENERATING,operation_id="lost-worker",generation=item.generation+1)
        stored.representations[1]=stuck.to_dict(); workspace.repository.update_representations(stored.project_id,stored.representations)
        recovered=client.get(f'/api/projects/{stored.project_id}').json()["representations"][1]
        assert recovered["status"]=="fallback" and "interrupted" in recovered["error"].lower()
        assert recovered["generation"]==stuck.generation+1


def test_websocket_replay_is_monotonic_and_deduplicable(tmp_path):
    app=create_app(storage_mode="sqlite",db_path=tmp_path/"db",artifact_dir=tmp_path/"a")
    with TestClient(app) as client:
        project=create(client); events=app.state.workspace.repository.get_events_after(project["projectId"],0)
        after=events[-3].event_id
        with client.websocket_connect(f'/api/projects/{project["projectId"]}/events?afterEventId={after}') as socket:
            replay=[socket.receive_json() for _ in range(2)]
        assert [x["eventId"] for x in replay]==[after+1,after+2]
        assert len({x.event_id for x in events})==len(events)


def test_event_broker_drops_a_slow_subscriber_without_blocking_publish(tmp_path):
    app=create_app(storage_mode="sqlite",db_path=tmp_path/"db",artifact_dir=tmp_path/"a")
    broker=EventBroker(app.state.workspace.repository,listener_queue_size=1,event_cache_size=2)
    queue=asyncio.Queue(maxsize=1)
    broker.listeners["project-x"]={queue}
    first=StoredEvent(1,"project-x",1,"first",[],{},"2026-09-14T00:00:00Z")
    second=StoredEvent(2,"project-x",1,"second",[],{},"2026-09-14T00:00:01Z")

    async def publish():
        await broker.publish_committed(first)
        await asyncio.wait_for(broker.publish_committed(second),timeout=.1)

    asyncio.run(publish())

    assert queue not in broker.listeners["project-x"]
    assert len(broker.events["project-x"])==2


def test_pending_state_evicts_the_oldest_entry_at_its_bound():
    pending={}
    for index in range(3):
        _remember_bounded(pending,f"item-{index}",index,max_entries=2)

    assert pending=={"item-1":1,"item-2":2}


def test_modification_lock_cannot_be_replaced_while_an_operation_holds_it():
    workspace=create_app(storage_mode="memory").state.workspace
    first=workspace.try_modification_lock("project-x")

    assert first is not None
    assert workspace.try_modification_lock("project-x") is None
    assert workspace.modification_locks["project-x"][0] is first

    workspace.release_modification_lock("project-x",first)

    assert "project-x" not in workspace.modification_locks
    replacement=workspace.try_modification_lock("project-x")
    assert replacement is not None and replacement is not first
    workspace.release_modification_lock("project-x",replacement)


def test_different_project_objectives_are_not_globally_serialized():
    workspace=create_app(storage_mode="memory").state.workspace
    active=0
    maximum=0

    async def controlled_create(body):
        nonlocal active,maximum
        active+=1
        maximum=max(maximum,active)
        await asyncio.sleep(.05)
        active-=1
        return body.objective

    workspace._create_serialized=controlled_create

    async def create_both():
        return await asyncio.gather(
            workspace.create(CreateProjectBody(objective="Design a temperature controlled fan")),
            workspace.create(CreateProjectBody(objective="Design a low voltage irrigation pump")),
        )

    assert asyncio.run(create_both())==[
        "Design a temperature controlled fan",
        "Design a low voltage irrigation pump",
    ]
    assert maximum==2
