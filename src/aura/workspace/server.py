from __future__ import annotations

import argparse
import asyncio
import webbrowser
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from aura.engineering_graph.model import EngineeringGraph, EntityKind
from aura.capabilities import CAPABILITY_MANIFEST, classify_objective
from aura.engineering_graph.serialization import graph_to_dict
from aura.engineering_graph.serialization import patch_to_dict
from aura.infrastructure.persistence.project_repository import (
    CorruptProjectData, PersistenceFailure, ProjectRepository, SQLiteProjectRepository,
    StoredEvent, StoredProject, UnsupportedSchemaVersion,
)
from aura.planner.live import LivePlanner, PlanningOutcome
from aura.planner.schemas import ProjectRequest
from aura.planner.service import PlannerService
from aura.verification.service import VerificationService
from .bridge import WorkspaceBridge
from .assembly import irrigation_assembly
from .events import WorkspaceEvent
from .representation_service import RepresentationService, initial_records, irrigation_specs
from .representations import RepresentationRecord, RepresentationStatus
from .modifications import ModificationProposal,inverse_proposal,propose


class CreateProjectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=8)
    planningMode: str = "deterministic_test"


class ModificationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selectedComponentId: str
    request: str = Field(min_length=8)


class EventEnvelope(BaseModel):
    eventId: int = Field(gt=0)
    projectId: str
    revision: int = Field(ge=0)
    type: str
    semanticIds: list[str]
    payload: dict[str, Any]
    timestamp: str


class RepresentationUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    error: Optional[str] = None
    metrics: dict[str, float] = Field(default_factory=dict)

class ProposalBody(BaseModel):
    projectId:str;baseRevision:int;selectedSemanticIds:list[str];request:str=Field(min_length=5);mode:str="automatic"


class EventBroker:
    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository
        self.events: dict[str, list[EventEnvelope]] = {}
        self.listeners: dict[str, set[asyncio.Queue[EventEnvelope]]] = {}

    def reset(self, project_id: str) -> None:
        self.events[project_id] = []

    async def publish_committed(self, event: StoredEvent) -> EventEnvelope:
        envelope = EventEnvelope(eventId=event.event_id, projectId=event.project_id,
            revision=event.revision, type=event.type, semanticIds=event.semantic_ids,
            payload=event.payload, timestamp=event.timestamp)
        self.events.setdefault(event.project_id, []).append(envelope)
        for queue in tuple(self.listeners.get(event.project_id, set())):
            await queue.put(envelope)
        return envelope

    def replay(self, project_id: str, after: int) -> list[EventEnvelope]:
        return [EventEnvelope(eventId=item.event_id, projectId=item.project_id, revision=item.revision,
            type=item.type, semanticIds=item.semantic_ids, payload=item.payload, timestamp=item.timestamp)
            for item in self.repository.get_events_after(project_id, after)]


class WorkspaceApplication:
    def __init__(self, provider: Any | None = None, planner_timeout: float | None = None,
                 repository: ProjectRepository | None = None, storage_mode: str | None = None,
                 db_path: str | Path | None = None, artifact_dir: Path | None = None) -> None:
        from aura.app.config import Settings, migrate_legacy_workspace_data
        settings = Settings()
        self.provider = provider
        if planner_timeout is None:
            planner_timeout = settings.planner_timeout
        self.planner_timeout = planner_timeout
        mode = storage_mode or settings.workspace_storage_mode
        if mode not in {"sqlite", "memory"}: raise ValueError(f"Unsupported workspace storage mode: {mode}")
        database = ":memory:" if mode == "memory" else str(db_path or settings.workspace_db_path)
        if mode != "memory" and db_path is None and artifact_dir is None:
            migrate_legacy_workspace_data(settings)
        self.repository = repository or SQLiteProjectRepository(database, artifact_dir or settings.workspace_artifact_dir)
        self.broker = EventBroker(self.repository)
        self.representation_service = RepresentationService(self.repository)
        self.modification_proposals:dict[str,ModificationProposal]={}
        self.modification_locks:dict[str,threading.Lock]={}

    def _request(self, objective: str) -> ProjectRequest:
        words=[word.capitalize() for word in objective.strip().rstrip(".").split() if word.lower() not in {"design","build","make","a","an","the","small"}]
        name=" ".join(words[:7]) or "Low-voltage Mechatronic Project"
        if "irrigation" in objective.lower(): name="Automatic Irrigation System"
        return ProjectRequest(name,objective,("Use isolated low-voltage DC power","Provide the requested sensing or actuation behavior"),assumptions=("Exact component selection and mechanical fit require implementation validation",))

    def plan(self, body: CreateProjectBody) -> PlanningOutcome:
        from aura.app.config import Settings
        fallback_enabled = Settings().deterministic_fallback
        request = self._request(body.objective)
        if body.planningMode == "live_model":
            provider = self.provider or self._default_provider()
            if provider is not None:
                outcome = LivePlanner(provider, self.planner_timeout).plan(request)
                if outcome.mode == "deterministic_fallback" and not fallback_enabled:
                    raise RuntimeError(outcome.fallback_reason or "live planning failed")
                return outcome
            if not fallback_enabled:
                raise RuntimeError("live model is unavailable and deterministic fallback is disabled")
        mode = "deterministic_test" if body.planningMode == "deterministic_test" else "deterministic_fallback"
        reason = None if mode == "deterministic_test" else "live model was not configured"
        return PlanningOutcome(PlannerService().plan(request), mode, reason)

    def _default_provider(self) -> Any | None:
        try:
            from aura.app.config import Settings
            from aura.infrastructure.llm.ollama import OllamaConversationModel
            from aura.infrastructure.llm.provider import ConversationModelAdapter
            settings = Settings()
            if settings.planner_provider != "ollama":
                return None
            model = settings.planner_model
            return ConversationModelAdapter(OllamaConversationModel(
                model, settings.ollama_base_url, max(2, int(self.planner_timeout) - 1),
                settings.ollama_context_length))
        except Exception:
            return None

    async def create(self, body: CreateProjectBody) -> StoredProject:
        try:
            outcome = await run_in_threadpool(self.plan, body)
        except ValueError as exc:
            detail=exc.args[0] if exc.args and isinstance(exc.args[0],dict) else {"status":"UNSUPPORTED","reasons":[str(exc)]}
            raise HTTPException(422,detail=detail) from exc
        except RuntimeError as exc:
            raise HTTPException(503, detail=str(exc)) from exc
        plan = outcome.plan
        project_id = plan.entities[0].id
        event_drafts = [{"type": "project.started", "payload": {"planningMode": outcome.mode}, "semantic_ids": []}]
        if outcome.mode == "live_model":
            event_drafts.append({"type": "planning.live_model", "payload": {"message": "Planning with live model"}, "semantic_ids": []})
        elif outcome.mode == "deterministic_fallback":
            event_drafts.append({"type": "task.fallback_used", "payload": {"reason": outcome.fallback_reason}, "semantic_ids": []})
        verified = VerificationService().verify(plan)
        if not verified.accepted:
            raise HTTPException(422, detail=list(verified.reasons))
        bridge = WorkspaceBridge()
        graph = bridge.commit(EngineeringGraph(project_id), verified)
        now = datetime.now(timezone.utc).isoformat()
        specs = irrigation_specs(graph)
        representations = initial_records(project_id, len(graph.revisions), specs)
        record = StoredProject(project_id, body.objective, outcome.mode, outcome.fallback_reason, "ready", graph,
            [item.to_dict() for item in representations], now, now)
        for event in bridge.events:
            if event.type == "project.started":
                continue
            event_drafts.append(self._event_draft(event, graph))
        verification = {"state": verified.state.value, "decision": verified.decision.value,
            "reasons": list(verified.reasons), "findings": [finding.__dict__ | {"state": finding.state.value} for finding in verified.findings]}
        try:
            committed = self.repository.save_commit(record, verified.patch, verification, event_drafts)  # type: ignore[arg-type]
        except PersistenceFailure as exc:
            raise HTTPException(503, detail={"code": "persistence_failure", "message": str(exc)}) from exc
        self.broker.reset(project_id)
        for event in committed: await self.broker.publish_committed(event)
        completed = await run_in_threadpool(self.representation_service.persist_specs, project_id,
            len(graph.revisions), representations, specs)
        record.representations = [item.to_dict() for item in completed]
        self.repository.update_representations(project_id, record.representations)
        representation_events=[]
        for item in completed:
            representation_events.append({"type":"representation.requested","semantic_ids":list(item.semantic_ids),
                "payload":{"representationId":item.representation_id,"type":item.type.value}})
            if item.type.value == "circuit_schematic":
                representation_events.append(
                    {"type":"representation.generating","semantic_ids":list(item.semantic_ids),"payload":{"representationId":item.representation_id}})
                if item.status is RepresentationStatus.FALLBACK:
                    representation_events.append(
                        {"type":"representation.failed","semantic_ids":list(item.semantic_ids),"payload":{"representationId":item.representation_id,"error":item.error}})
                representation_events.append(
                    {"type":f"representation.{item.status.value}","semantic_ids":list(item.semantic_ids),"payload":{"representationId":item.representation_id,"artifactId":item.artifact_id,"error":item.error}})
        for event in self.repository.append_events(project_id,len(graph.revisions),representation_events):
            await self.broker.publish_committed(event)
        return record

    def _event_draft(self, event: WorkspaceEvent, graph: EngineeringGraph) -> dict[str, Any]:
        semantic_ids = []
        if event.entity_id:
            semantic_ids.append(event.entity_id)
        semantic_ids.extend(value for value in event.payload.get("entity_ids", []) if value not in semantic_ids)
        return {"type": event.type, "semantic_ids": semantic_ids, "payload": event.payload,
                "revision": len(graph.revisions) if event.revision_id else 0, "timestamp": event.created_at}

    async def modify(self, project_id: str, body: ModificationBody) -> dict[str, Any]:
        record = self.repository.get_project(project_id)
        if record is None:
            raise HTTPException(404, "Project not found")
        try:
            selected = record.graph.get(body.selectedComponentId)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        if selected.id != "component-driver" or "mosfet" not in body.request.lower():
            raise HTTPException(422, "This vertical slice supports only the relay-to-MOSFET modification")
        before = {"id": selected.id, "name": selected.name, "revision": len(record.graph.revisions)}
        patch = PlannerService().propose_mosfet_replacement(record.graph)
        result = VerificationService().verify_modification(record.graph, patch)
        bridge = WorkspaceBridge()
        updated = bridge.commit(record.graph, result)
        previous = [RepresentationRecord.from_dict(item) for item in record.representations]
        circuit_before = next(item for item in previous if item.type.value == "circuit_schematic")
        circuit_after = await run_in_threadpool(self.representation_service.regenerate_circuit, updated, circuit_before)
        representations = [circuit_after.to_dict() if item.representation_id == circuit_before.representation_id else item.to_dict() for item in previous]
        updated_record = StoredProject(record.project_id, record.objective, record.planning_mode,
            record.fallback_reason, "ready", updated, representations, record.created_at,
            datetime.now(timezone.utc).isoformat())
        event_drafts = [self._event_draft(event, updated) for event in bridge.events]
        event_drafts.extend([
            {"type":"representation.stale","semantic_ids":["component-driver"],"payload":{"representationId":circuit_before.representation_id}},
            {"type":"representation.generating","semantic_ids":list(circuit_after.semantic_ids),"payload":{"representationId":circuit_after.representation_id}},
        ])
        if circuit_after.status is RepresentationStatus.FALLBACK:
            event_drafts.append({"type":"representation.failed","semantic_ids":list(circuit_after.semantic_ids),
                "payload":{"representationId":circuit_after.representation_id,"error":circuit_after.error}})
        event_drafts.append({"type":f"representation.{circuit_after.status.value}","semantic_ids":list(circuit_after.semantic_ids),
            "payload":{"representationId":circuit_after.representation_id,"artifactId":circuit_after.artifact_id,"error":circuit_after.error}})
        verification = {"state": result.state.value, "decision": result.decision.value,
            "reasons": list(result.reasons), "findings": [finding.__dict__ | {"state": finding.state.value} for finding in result.findings]}
        try:
            committed = self.repository.save_commit(updated_record, result.patch, verification, event_drafts)  # type: ignore[arg-type]
        except PersistenceFailure as exc:
            raise HTTPException(503, detail={"code": "persistence_failure", "message": str(exc)}) from exc
        for event in committed: await self.broker.publish_committed(event)
        after_entity = updated.get(selected.id)
        after = {"id": after_entity.id, "name": after_entity.name, "revision": len(updated.revisions)}
        return {"projectId": project_id, "before": before, "after": after,
                "summary": patch.summary, "rerunChecks": [finding.check for finding in result.findings]}


def create_app(provider: Any | None = None, planner_timeout: float | None = None,
               repository: ProjectRepository | None = None, storage_mode: str | None = None,
               db_path: str | Path | None = None, artifact_dir: Path | None = None) -> FastAPI:
    application = WorkspaceApplication(provider, planner_timeout, repository, storage_mode, db_path, artifact_dir)
    app = FastAPI(title="AURA Engineering Workspace", version="0.2.0")
    app.state.workspace = application
    web_root = Path(__file__).with_name("web")
    app.mount("/assets", StaticFiles(directory=web_root), name="workspace-assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(web_root / "index.html")

    @app.post("/api/projects", status_code=201)
    async def create_project(body: CreateProjectBody) -> dict[str, Any]:
        record = await application.create(body)
        return _project_payload(record)

    @app.get("/api/projects")
    def list_projects() -> list[dict[str, Any]]:
        return [_project_payload(record, concise=True) for record in application.repository.list_projects()]

    @app.get("/api/capabilities")
    def get_capabilities()->dict[str,Any]: return CAPABILITY_MANIFEST

    @app.post("/api/capabilities/classify")
    def classify(body:CreateProjectBody)->dict[str,Any]: return classify_objective(body.objective)

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        record = _record(application, project_id)
        return _project_payload(record)

    @app.get("/api/projects/{project_id}/graph")
    def get_graph(project_id: str) -> dict[str, Any]:
        return graph_to_dict(_record(application, project_id).graph)

    @app.get("/api/projects/{project_id}/revisions")
    def get_revisions(project_id: str) -> list[dict[str, Any]]:
        _record(application, project_id)
        return [{"revision": item["revision"], "revisionId": item["revisionId"],
                 "patchId": item["patch"].id, "summary": item["patch"].summary,
                 "verification": item["verification"], "createdAt": item["createdAt"]}
                for item in application.repository.list_revisions(project_id)]

    @app.post("/api/projects/{project_id}/modifications")
    async def modify_project(project_id: str, body: ModificationBody) -> dict[str, Any]:
        return await application.modify(project_id, body)

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str) -> dict[str, Any]:
        artifact = application.repository.get_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(404, detail={"code": "artifact_not_found", "artifactId": artifact_id})
        return {"artifactId": artifact.artifact_id, "projectId": artifact.project_id,
                "revision": artifact.revision, "componentIds": artifact.component_ids,
                "representationType": artifact.representation_type, "format": artifact.format,
                "status": artifact.status, "contentHash": artifact.content_hash,
                "relativePath": artifact.relative_path, "generator": artifact.generator,
                "generatorVersion": artifact.generator_version, "createdAt": artifact.created_at,
                "error": artifact.error}

    @app.get("/api/artifacts/{artifact_id}/content")
    def get_artifact_content(artifact_id: str) -> Response:
        artifact = application.repository.get_artifact(artifact_id)
        if artifact is None or artifact.status != "ready" or not artifact.relative_path:
            raise HTTPException(404, detail={"code":"artifact_content_not_found","artifactId":artifact_id})
        content = application.repository.resolve_artifact_path(artifact.relative_path).read_bytes()  # type: ignore[attr-defined]
        media = "application/json" if artifact.format in {"circuit-json","representation-spec"} else "application/octet-stream"
        return Response(content, media_type=media)

    @app.get("/api/projects/{project_id}/assembly")
    def get_assembly(project_id: str) -> dict[str, Any]:
        return irrigation_assembly(_record(application, project_id).graph)

    @app.post("/api/projects/{project_id}/representations/{representation_id}/status")
    async def update_representation(project_id: str, representation_id: str, body: RepresentationUpdateBody) -> dict[str, Any]:
        record = _record(application, project_id)
        items = [RepresentationRecord.from_dict(item) for item in record.representations]
        try: current = next(item for item in items if item.representation_id == representation_id)
        except StopIteration as exc: raise HTTPException(404, "Representation not found") from exc
        try: updated = current.transition(RepresentationStatus(body.status), error=body.error)
        except ValueError as exc: raise HTTPException(409, str(exc)) from exc
        record.representations = [updated.to_dict() if item.representation_id == representation_id else item.to_dict() for item in items]
        application.repository.update_representations(project_id,record.representations)
        event_type=f"representation.{updated.status.value}"
        events=application.repository.append_events(project_id,updated.revision,[{"type":event_type,"semantic_ids":list(updated.semantic_ids),
            "payload":{"representationId":representation_id,"metrics":body.metrics,"error":body.error}}])
        for event in events: await application.broker.publish_committed(event)
        return updated.to_dict()

    @app.post("/api/projects/{project_id}/modification-proposals",status_code=201)
    async def create_modification_proposal(project_id:str,body:ProposalBody)->dict[str,Any]:
        record=_record(application,project_id)
        if body.projectId!=project_id: raise HTTPException(422,"Project ID mismatch")
        try: proposal=propose(record.graph,body.baseRevision,body.selectedSemanticIds,body.request,body.mode)
        except ValueError as exc:
            code=str(exc);status=409 if code=="stale_revision" else 422
            raise HTTPException(status,detail={"code":code,"currentRevision":len(record.graph.revisions)}) from exc
        application.modification_proposals[proposal.proposal_id]=proposal
        for event in application.repository.append_events(project_id,len(record.graph.revisions),[
            {"type":"modification.requested","semantic_ids":body.selectedSemanticIds,"payload":{"request":body.request}},
            {"type":"modification.preview_ready","semantic_ids":list(proposal.affected_ids),"payload":{"proposalId":proposal.proposal_id}}]): await application.broker.publish_committed(event)
        return proposal.to_dict()

    @app.delete("/api/projects/{project_id}/modification-proposals/{proposal_id}")
    async def cancel_modification(project_id:str,proposal_id:str)->dict[str,bool]:
        proposal=application.modification_proposals.pop(proposal_id,None)
        if proposal:
            for event in application.repository.append_events(project_id,proposal.base_revision,[{"type":"modification.cancelled","semantic_ids":list(proposal.target_ids),"payload":{"proposalId":proposal_id}}]): await application.broker.publish_committed(event)
        return {"cancelled":bool(proposal)}

    @app.post("/api/projects/{project_id}/modification-proposals/{proposal_id}/commit")
    async def commit_modification(project_id:str,proposal_id:str)->dict[str,Any]:
        proposal=application.modification_proposals.get(proposal_id)
        if not proposal: raise HTTPException(404,"Proposal not found")
        lock=application.modification_locks.setdefault(project_id,threading.Lock())
        if not lock.acquire(blocking=False): raise HTTPException(409,detail={"code":"modification_in_progress"})
        try:
            record=_record(application,project_id)
            if len(record.graph.revisions)!=proposal.base_revision: raise HTTPException(409,detail={"code":"stale_revision","currentRevision":len(record.graph.revisions)})
            result=VerificationService().verify_modification(record.graph,proposal.patch)
            if not result.accepted or result.patch is None: raise HTTPException(422,detail={"code":"verification_rejected","reasons":list(result.reasons)})
            updated=WorkspaceBridge().commit(record.graph,result)
            reps=[]; lifecycle=[]
            for item in record.representations:
                current=RepresentationRecord.from_dict(item)
                if current.representation_id not in proposal.regenerate:
                    reps.append(current.to_dict());continue
                regenerated=await run_in_threadpool(application.representation_service.regenerate,updated,current)
                reps.append(regenerated.to_dict())
                lifecycle.extend([
                    {"type":"representation.stale","semantic_ids":list(current.semantic_ids),"payload":{"representationId":current.representation_id}},
                    {"type":"representation.generating","semantic_ids":list(current.semantic_ids),"payload":{"representationId":current.representation_id}},
                ])
                if regenerated.status is RepresentationStatus.FALLBACK:
                    lifecycle.append({"type":"representation.failed","semantic_ids":list(current.semantic_ids),"payload":{"representationId":current.representation_id,"error":regenerated.error}})
                lifecycle.append({"type":f"representation.{regenerated.status.value}","semantic_ids":list(current.semantic_ids),"payload":{"representationId":current.representation_id,"artifactId":regenerated.artifact_id,"error":regenerated.error}})
            updated_record=StoredProject(record.project_id,record.objective,record.planning_mode,record.fallback_reason,"ready",updated,reps,record.created_at,datetime.now(timezone.utc).isoformat())
            diff={"changed":list(proposal.operations),"regenerated":list(proposal.regenerate),"affected":list(proposal.affected_ids),"unchanged":list(proposal.unaffected)}
            drafts=[{"type":"modification.committed","semantic_ids":list(proposal.affected_ids),"payload":{"proposalId":proposal_id,"diff":diff}},{"type":"revision.committed","semantic_ids":list(proposal.affected_ids),"payload":{"diff":diff}},*lifecycle]
            verification={"outcome":proposal.verification,"diff":diff,"kind":"undo" if proposal.mode=="undo" else "modification"}
            committed=application.repository.save_commit(updated_record,result.patch,verification,drafts)
            for event in committed:await application.broker.publish_committed(event)
            application.modification_proposals.pop(proposal_id,None)
            return {"projectId":project_id,"revision":len(updated.revisions),"summary":proposal.summary,"diff":diff,"representations":reps}
        finally:lock.release()

    @app.post("/api/projects/{project_id}/revisions/undo")
    async def undo_revision(project_id:str)->dict[str,Any]:
        record=_record(application,project_id)
        revisions=application.repository.list_revisions(project_id)
        source=revisions[-1] if revisions and revisions[-1].get("verification",{}).get("kind")=="modification" else None
        if source is None: raise HTTPException(409,detail={"code":"nothing_to_undo"})
        try: proposal=inverse_proposal(record.graph,source)
        except ValueError as exc: raise HTTPException(409,detail={"code":str(exc)}) from exc
        application.modification_proposals[proposal.proposal_id]=proposal
        return await commit_modification(project_id,proposal.proposal_id)

    @app.websocket("/api/projects/{project_id}/events")
    async def events(websocket: WebSocket, project_id: str,
                     after_event_id: int = Query(0, alias="afterEventId", ge=0)) -> None:
        await websocket.accept()
        queue: asyncio.Queue[EventEnvelope] = asyncio.Queue()
        application.broker.listeners.setdefault(project_id, set()).add(queue)
        try:
            for event in application.broker.replay(project_id, after_event_id):
                await websocket.send_json(event.model_dump())
            while True:
                event = await queue.get()
                await websocket.send_json(event.model_dump())
        except WebSocketDisconnect:
            pass
        finally:
            application.broker.listeners.get(project_id, set()).discard(queue)
    return app


def _record(application: WorkspaceApplication, project_id: str) -> StoredProject:
    try:
        record = application.repository.get_project(project_id)
    except (CorruptProjectData, UnsupportedSchemaVersion) as exc:
        raise HTTPException(500, detail={"code": "stored_data_error", "message": str(exc)}) from exc
    if record is None: raise HTTPException(404, "Project not found")
    return record


def _project_payload(record: StoredProject, concise: bool = False) -> dict[str, Any]:
    graph = record.graph
    return {"projectId": graph.project_id, "objective": record.objective,
            "capability": classify_objective(record.objective),
            "planningMode": record.planning_mode, "fallbackReason": record.fallback_reason,
            "revision": len(graph.revisions), "status": record.status,
            "createdAt": record.created_at, "updatedAt": record.updated_at,
            **({} if concise else {"representations": record.representations})}


def main() -> None:
    from aura.app.config import Settings
    settings = Settings()
    parser = argparse.ArgumentParser(description="Run the AURA browser workspace")
    parser.add_argument("--host", default=settings.workspace_host)
    parser.add_argument("--port", default=settings.workspace_port, type=int)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args()
    if args.open_browser:
        webbrowser.open(f"http://{args.host}:{args.port}")
    import uvicorn
    uvicorn.run("aura.workspace.server:create_app", host=args.host, port=args.port, reload=False, factory=True)


if __name__ == "__main__":
    main()
