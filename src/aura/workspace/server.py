from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import webbrowser
import threading
import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
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
from aura.verification.catalogue import CATALOGUE, search as search_catalogue
from aura.verification.results import VerificationState
from .bridge import WorkspaceBridge
from .assembly import engineering_assembly
from .events import WorkspaceEvent
from .representation_service import RepresentationService, initial_records, representation_specs
from .representations import RepresentationRecord, RepresentationStatus
from .modifications import LiveModificationPlanner,ModificationProposal,inverse_proposal,propose
from .narration import NarrationService

LOGGER = logging.getLogger("aura.workspace")


class CreateProjectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=8)
    planningMode: str = "deterministic_test"
    operationId: Optional[str] = None


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
    historical: bool = False


class RepresentationUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    error: Optional[str] = None
    metrics: dict[str, float] = Field(default_factory=dict)
    projectId: Optional[str] = None
    revision: Optional[int] = None
    operationId: Optional[str] = None
    generation: Optional[int] = None

class ProposalBody(BaseModel):
    projectId:str;baseRevision:int;selectedSemanticIds:list[str];request:str=Field(min_length=5);mode:str="automatic";operationId:Optional[str]=None


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
            type=item.type, semanticIds=item.semantic_ids, payload=item.payload, timestamp=item.timestamp,historical=True)
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
        if mode not in {"sqlite", "memory", "postgres"}: raise ValueError(f"Unsupported workspace storage mode: {mode}")
        database = ":memory:" if mode == "memory" else str(db_path or settings.workspace_db_path)
        if mode != "memory" and db_path is None and artifact_dir is None:
            migrate_legacy_workspace_data(settings)
        if repository is not None:
            self.repository = repository
        else:
            from aura.infrastructure.artifacts import GcsArtifactStore, LocalFilesystemArtifactStore
            if settings.artifact_storage_mode == "gcs":
                artifact_store = GcsArtifactStore(settings.gcs_bucket, timeout=settings.artifact_timeout)
            elif settings.artifact_storage_mode == "local":
                artifact_store = LocalFilesystemArtifactStore(artifact_dir or settings.workspace_artifact_dir)
            else:
                raise ValueError(f"Unsupported artifact storage mode: {settings.artifact_storage_mode}")
            if mode == "postgres":
                from aura.infrastructure.persistence.postgres_repository import PostgresProjectRepository
                dsn = settings.database_url
                if not dsn:
                    from psycopg.conninfo import make_conninfo
                    dsn = make_conninfo(host=settings.db_host, port=settings.db_port, dbname=settings.db_name,
                        user=settings.db_user, password=settings.db_password)
                self.repository = PostgresProjectRepository(dsn, artifact_store, settings.db_pool_size,
                    settings.db_max_overflow, settings.db_pool_timeout)
            else:
                self.repository = SQLiteProjectRepository(database, artifact_dir or settings.workspace_artifact_dir, artifact_store)
        self.broker = EventBroker(self.repository)
        from .representation_service import CircuitGeneratorAdapter
        self.representation_service = RepresentationService(self.repository, CircuitGeneratorAdapter(timeout=settings.circuit_timeout))
        self.narration_service = NarrationService()
        self.modification_proposals:dict[str,ModificationProposal]={}
        self.modification_operations:dict[str,ModificationProposal]={}
        self.modification_locks:dict[str,threading.Lock]={}
        self.active_representation_operations:set[str]=set()

    def _request(self, objective: str) -> ProjectRequest:
        words=[word.capitalize() for word in objective.strip().rstrip(".").split() if word.lower() not in {"design","build","make","a","an","the","small"}]
        name=" ".join(words[:7]) or "Low-voltage Mechatronic Project"
        return ProjectRequest(name,objective,("Use isolated low-voltage DC power","Provide the requested sensing or actuation behavior"),assumptions=("Exact component selection and mechanical fit require implementation validation",))

    def plan(self, body: CreateProjectBody) -> PlanningOutcome:
        from aura.app.config import Settings
        fallback_enabled = Settings().deterministic_fallback
        request = self._request(body.objective)
        if body.planningMode == "live_model":
            provider = self.provider or self._default_provider()
            if provider is not None:
                self.provider=provider
                outcome = LivePlanner(provider, self.planner_timeout).plan(request)
                if outcome.mode=="deterministic_fallback" and outcome.fallback_reason and any(term in outcome.fallback_reason for term in ("Application Default Credentials","ADC/IAM access")):
                    raise RuntimeError(outcome.fallback_reason)
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
            settings = Settings()
            if settings.planner_provider=="vertex":
                from aura.infrastructure.llm.vertex import VertexPlannerProvider
                project=settings.gcp_project
                if not project:
                    try:
                        import google.auth
                        _,project=google.auth.default(scopes=[VertexPlannerProvider.SCOPE])
                    except Exception as exc:raise RuntimeError("Vertex Planner ADC is unavailable; run: gcloud auth application-default login") from exc
                if not project or not settings.vertex_model:raise RuntimeError("Vertex Planner requires an ADC project or AURA_GCP_PROJECT and AURA_VERTEX_MODEL")
                return VertexPlannerProvider(project,settings.gcp_location,settings.vertex_model,settings.vertex_timeout)
            if settings.planner_provider=="deterministic":return None
            raise RuntimeError(f"Unsupported Planner provider: {settings.planner_provider}")
        except RuntimeError:raise
        except Exception as exc:raise RuntimeError(f"Could not initialize Planner provider: {exc}") from exc

    async def create(self, body: CreateProjectBody) -> StoredProject:
        if body.operationId:
            completed=self.find_operation("project.operation_completed",body.operationId)
            if completed:
                existing=self.repository.get_project(completed.payload["projectId"])
                if existing:return existing
        try:
            outcome = await run_in_threadpool(self.plan, body)
        except ValueError as exc:
            detail=exc.args[0] if exc.args and isinstance(exc.args[0],dict) else {"status":"UNSUPPORTED","reasons":[str(exc)]}
            raise HTTPException(422,detail=detail) from exc
        except RuntimeError as exc:
            raise HTTPException(503, detail=str(exc)) from exc
        plan = outcome.plan
        capability = classify_objective(body.objective)["status"]
        if capability in {"SUPPORTED", "SUPPORTED_WITH_LIMITATIONS"}:
            component_entities=[item for item in plan.entities if item.kind is EntityKind.COMPONENT]
            if not component_entities:
                raise HTTPException(422,detail={"status":"PLANNING_FAILED","reasons":["Supported Planner output contained no semantic components after bounded repair/fallback."]})
        project_id = plan.entities[0].id
        existing=self.repository.get_project(project_id)
        if body.planningMode=="deterministic_test" and existing is not None:
            return existing
        planner_metadata = dict(outcome.provider_metadata or {})
        planner_metadata.update({"provider": "vertex" if outcome.mode == "live_model" else "deterministic", "fallbackUsed": outcome.mode != "live_model", "planId": plan.patch.id, "componentCount": len(plan.components), "relationshipCount": len(plan.relationships)})
        event_drafts = [{"type": "project.started", "payload": {"planningMode": outcome.mode,"operationId":body.operationId,"planner":planner_metadata}, "semantic_ids": []}]
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
        specs = representation_specs(graph)
        representations = initial_records(project_id, len(graph.revisions), specs)
        record = StoredProject(project_id, body.objective, outcome.mode, outcome.fallback_reason, "building", graph,
            [item.to_dict() for item in representations], now, now)
        for event in bridge.events:
            if event.type in {"project.started", "project.ready"}:
                continue
            event_drafts.append(self._event_draft(event, graph))
        if body.operationId:event_drafts.append({"type":"project.operation_completed","semantic_ids":[project_id],"payload":{"operationId":body.operationId,"projectId":project_id,"revision":len(graph.revisions)}})
        verification = {"state": verified.state.value, "decision": verified.decision.value,
            "reasons": list(verified.reasons), "findings": [finding.__dict__ | {"state": finding.state.value} for finding in verified.findings]}
        try:
            committed = self.repository.save_commit(record, verified.patch, verification, event_drafts)  # type: ignore[arg-type]
        except PersistenceFailure as exc:
            raise HTTPException(503, detail={"code": "persistence_failure", "message": str(exc)}) from exc
        self.broker.reset(project_id)
        await self.publish_with_narration(committed,graph,record.representations)
        completed = await run_in_threadpool(self.representation_service.persist_specs, project_id,
            len(graph.revisions), representations, specs)
        record.representations = [item.to_dict() for item in completed]
        self.repository.update_representations(project_id, record.representations)
        physical_ids={entity.id for entity in graph.find(kind=EntityKind.COMPONENT)}
        ready_physical={semantic_id for item in completed if item.type.value=="mechanical_3d" and item.status is RepresentationStatus.READY for semantic_id in item.semantic_ids}
        assembly=engineering_assembly(graph)
        circuit_specs=[spec for spec in specs if spec.kind.value=="circuit_schematic"]
        circuit_fidelity=all(spec.payload.get("fidelity",{}).get("portsComplete") and spec.payload.get("fidelity",{}).get("netsComplete") for spec in circuit_specs)
        critical_semantic=any(item.severity=="critical" and item.state is VerificationState.FAILED for item in verified.findings)
        physical_complete=bool(physical_ids) and physical_ids <= ready_physical and len(assembly.get("parts",())) >= len(physical_ids)
        required_failed = any(item.status is RepresentationStatus.FALLBACK for item in completed) or not physical_complete or not circuit_fidelity or critical_semantic
        record.status = "build_incomplete" if required_failed else ("ready_with_limitations" if capability == "SUPPORTED_WITH_LIMITATIONS" else "ready")
        self.repository.update_project_status(project_id, record.status)
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
        representation_committed=self.repository.append_events(project_id,len(graph.revisions),representation_events)
        await self.publish_with_narration(representation_committed,graph,record.representations)
        ready_event=self.repository.append_events(project_id,len(graph.revisions),[{"type":"project.ready" if not required_failed else "project.build_incomplete","semantic_ids":[project_id],"payload":{"status":record.status,"physicalComponentCount":len(physical_ids),"renderablePhysicalCount":len(ready_physical),"circuitFidelity":circuit_fidelity}}])
        await self.publish_with_narration(ready_event,graph,record.representations)
        return record

    async def publish_with_narration(self,committed:list[StoredEvent],graph:EngineeringGraph,
                                     representations:list[dict[str,Any]])->None:
        for event in committed: await self.broker.publish_committed(event)
        narrations=self.narration_service.events(committed,graph,representations)
        if not narrations:return
        drafts=[{"type":"narration.created","semantic_ids":list(item.semantic_ids),"payload":item.to_dict(),
                 "timestamp":item.created_at} for item in narrations]
        for event in self.repository.append_events(graph.project_id,len(graph.revisions),drafts):
            await self.broker.publish_committed(event)

    def find_operation(self,event_type:str,operation_id:str,project_id:str|None=None)->StoredEvent|None:
        projects=[self.repository.get_project(project_id)] if project_id else self.repository.list_projects()
        for project in (x for x in projects if x is not None):
            for event in reversed(self.repository.get_events_after(project.project_id,0)):
                if event.type==event_type and event.payload.get("operationId")==operation_id:return event
        return None

    def recover_interrupted(self,record:StoredProject)->StoredProject:
        changed=False;items=[]
        for value in record.representations:
            item=RepresentationRecord.from_dict(value)
            if item.status is RepresentationStatus.GENERATING and item.operation_id not in self.active_representation_operations:
                item=replace(item,status=RepresentationStatus.FALLBACK,error="Generation was interrupted; retry this representation.",generation=item.generation+1,operation_id=None);changed=True
            items.append(item.to_dict())
        if changed:self.repository.update_representations(record.project_id,items);record.representations=items
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
        await self.publish_with_narration(committed,updated,representations)
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

    @app.middleware("http")
    async def correlate_request(request, call_next):
        request_id=request.headers.get("X-Request-ID") or uuid4().hex
        started=time.perf_counter()
        try:
            response=await call_next(request); outcome=str(response.status_code)
        except Exception:
            LOGGER.exception(json.dumps({"requestId":request_id,"method":request.method,"path":request.url.path,"outcome":"exception"},separators=(",",":")))
            raise
        response.headers["X-Request-ID"]=request_id
        LOGGER.info(json.dumps({"requestId":request_id,"method":request.method,"path":request.url.path,"durationMs":round((time.perf_counter()-started)*1000,1),"outcome":outcome},separators=(",",":")))
        return response

    @app.get("/")
    def index() -> FileResponse:
        # The Vite renderer is the single production UI for browser tests and
        # the Electron shell.  The previous dashboard/iframe remains only as
        # source history and is no longer served to users.
        return FileResponse(web_root / "representation" / "index.html")

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status":"ok","version":os.getenv("AURA_VERSION","0.1.0"),"commit":os.getenv("AURA_BUILD_COMMIT","development"),"environment":"cloud" if os.getenv("AURA_CLOUD_MODE","false").lower()=="true" else "development"}

    @app.get("/health/ready")
    def health_ready() -> dict[str, str]:
        if not application.repository.is_ready():
            raise HTTPException(503, detail={"status": "not_ready"})
        return {"status": "ready"}

    @app.post("/api/projects", status_code=201)
    async def create_project(body: CreateProjectBody) -> dict[str, Any]:
        record = await application.create(body)
        return _project_payload(record)

    @app.get("/api/projects")
    def list_projects() -> list[dict[str, Any]]:
        return [_project_payload(record, concise=True) for record in application.repository.list_projects()]

    @app.get("/api/capabilities")
    def get_capabilities()->dict[str,Any]: return CAPABILITY_MANIFEST

    @app.get("/api/catalogue")
    def get_catalogue(family: Optional[str] = None, voltage: Optional[float] = None,
                      minimumCurrentMa: Optional[float] = None, interface: Optional[str] = None) -> list[dict[str, Any]]:
        return [item.to_dict() for item in search_catalogue(family=family, voltage=voltage,
            minimum_current_ma=minimumCurrentMa, interface=interface)]

    @app.get("/api/catalogue/{component_definition_id}")
    def get_catalogue_item(component_definition_id: str) -> dict[str, Any]:
        item=next((x for x in CATALOGUE if x.component_definition_id==component_definition_id),None)
        if item is None: raise HTTPException(404,detail={"code":"unknown_component_definition"})
        return item.to_dict()

    @app.post("/api/capabilities/classify")
    def classify(body:CreateProjectBody)->dict[str,Any]: return classify_objective(body.objective)

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        record = application.recover_interrupted(_record(application, project_id))
        return _project_payload(record)

    @app.get("/api/projects/{project_id}/graph")
    def get_graph(project_id: str) -> dict[str, Any]:
        return graph_to_dict(_record(application, project_id).graph)

    @app.get("/api/projects/{project_id}/provenance")
    def get_provenance(project_id: str) -> dict[str, Any]:
        _record(application, project_id)
        event=next((item for item in application.repository.get_events_after(project_id,0) if item.type=="project.started"),None)
        return {"projectId":project_id,"planner":dict(event.payload.get("planner",{})) if event else {}}

    @app.get("/api/projects/{project_id}/verification")
    def get_verification(project_id: str) -> dict[str, Any]:
        graph=_record(application,project_id).graph
        findings=graph.find(kind=EntityKind.VERIFICATION_RESULT); evidence=graph.find(kind=EntityKind.EVIDENCE)
        statuses=[x.value for x in VerificationState]
        return {"projectId":project_id,"revision":len(graph.revisions),
                "summary":{status:sum(x.verification_status==status for x in findings) for status in statuses},
                "findings":[x.metadata for x in findings],"evidence":[x.metadata for x in evidence]}

    @app.get("/api/projects/{project_id}/evidence/{evidence_id}")
    def get_evidence(project_id: str,evidence_id: str) -> dict[str, Any]:
        graph=_record(application,project_id).graph
        item=graph.entities.get(evidence_id)
        if item is None or item.kind is not EntityKind.EVIDENCE: raise HTTPException(404,"Evidence not found")
        return item.metadata

    @app.get("/api/projects/{project_id}/revisions")
    def get_revisions(project_id: str) -> list[dict[str, Any]]:
        _record(application, project_id)
        return [{"revision": item["revision"], "revisionId": item["revisionId"],
                 "patchId": item["patch"].id, "summary": item["patch"].summary,
                 "verification": item["verification"], "createdAt": item["createdAt"]}
                for item in application.repository.list_revisions(project_id)]

    @app.get("/api/projects/{project_id}/narrations")
    def get_narrations(project_id:str)->list[dict[str,Any]]:
        _record(application,project_id)
        return [item.payload for item in application.repository.get_events_after(project_id,0)
                if item.type=="narration.created"]

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
        try: content = application.repository.read_artifact(artifact_id)
        except (KeyError, CorruptProjectData) as exc:
            raise HTTPException(404, detail={"code":"artifact_content_not_found","artifactId":artifact_id}) from exc
        media = "application/json" if artifact.format in {"circuit-json","representation-spec"} else "application/octet-stream"
        return Response(content, media_type=media)

    @app.get("/api/projects/{project_id}/assembly")
    def get_assembly(project_id: str) -> dict[str, Any]:
        return engineering_assembly(_record(application, project_id).graph)

    @app.post("/api/projects/{project_id}/representations/{representation_id}/status")
    async def update_representation(project_id: str, representation_id: str, body: RepresentationUpdateBody) -> dict[str, Any]:
        record = _record(application, project_id)
        items = [RepresentationRecord.from_dict(item) for item in record.representations]
        try: current = next(item for item in items if item.representation_id == representation_id)
        except StopIteration as exc: raise HTTPException(404, "Representation not found") from exc
        if ((body.projectId is not None and body.projectId!=project_id) or
            (body.revision is not None and body.revision!=current.revision) or
            (body.operationId is not None and body.operationId!=current.operation_id) or
            (body.generation is not None and body.generation!=current.generation)):
            return {**current.to_dict(),"ignored":True,"reason":"stale_representation_result"}
        try: updated = current.transition(RepresentationStatus(body.status), error=body.error)
        except ValueError as exc: raise HTTPException(409, str(exc)) from exc
        record.representations = [updated.to_dict() if item.representation_id == representation_id else item.to_dict() for item in items]
        application.repository.update_representations(project_id,record.representations)
        if updated.status is RepresentationStatus.GENERATING and updated.operation_id:application.active_representation_operations.add(updated.operation_id)
        elif current.operation_id:application.active_representation_operations.discard(current.operation_id)
        event_type=f"representation.{updated.status.value}"
        events=application.repository.append_events(project_id,updated.revision,[{"type":event_type,"semantic_ids":list(updated.semantic_ids),
            "payload":{"representationId":representation_id,"metrics":body.metrics,"error":body.error}}])
        await application.publish_with_narration(events,record.graph,record.representations)
        return updated.to_dict()

    @app.post("/api/projects/{project_id}/representations/{representation_id}/retry")
    async def retry_representation(project_id:str,representation_id:str,idempotency_key:Optional[str]=Header(None,alias="Idempotency-Key"))->dict[str,Any]:
        record=_record(application,project_id)
        if idempotency_key:
            prior=application.find_operation("representation.operation_completed",idempotency_key,project_id)
            if prior:return prior.payload["result"]
        try: current=next(RepresentationRecord.from_dict(x) for x in record.representations if x["representationId"]==representation_id)
        except StopIteration as exc:raise HTTPException(404,"Representation not found") from exc
        if current.revision!=len(record.graph.revisions):raise HTTPException(409,detail={"code":"stale_representation_revision"})
        updated=await run_in_threadpool(application.representation_service.regenerate,record.graph,current)
        record.representations=[updated.to_dict() if x["representationId"]==representation_id else x for x in record.representations]
        application.repository.update_representations(project_id,record.representations)
        result=updated.to_dict();drafts=[{"type":f"representation.{updated.status.value}","semantic_ids":list(updated.semantic_ids),"payload":{"representationId":representation_id,"operationId":updated.operation_id}}]
        if idempotency_key:drafts.append({"type":"representation.operation_completed","semantic_ids":list(updated.semantic_ids),"payload":{"operationId":idempotency_key,"result":result}})
        events=application.repository.append_events(project_id,len(record.graph.revisions),drafts);await application.publish_with_narration(events,record.graph,record.representations)
        return result

    @app.post("/api/projects/{project_id}/modification-proposals",status_code=201)
    async def create_modification_proposal(project_id:str,body:ProposalBody)->dict[str,Any]:
        record=_record(application,project_id)
        if body.projectId!=project_id: raise HTTPException(422,"Project ID mismatch")
        if body.operationId and body.operationId in application.modification_operations:return application.modification_operations[body.operationId].to_dict()
        try:
            if record.planning_mode=="live_model" and application.provider is not None and hasattr(application.provider,"generate_structured"):
                try:proposal=await run_in_threadpool(LiveModificationPlanner(application.provider).propose,record.graph,body.baseRevision,body.selectedSemanticIds,body.request,body.mode)
                except Exception as model_exc:
                    if model_exc.__class__.__name__=="VertexAuthenticationError":raise HTTPException(503,detail={"code":"vertex_authentication_error","message":str(model_exc)}) from model_exc
                    proposal=propose(record.graph,body.baseRevision,body.selectedSemanticIds,body.request,body.mode)
            else:proposal=propose(record.graph,body.baseRevision,body.selectedSemanticIds,body.request,body.mode)
        except ValueError as exc:
            code=str(exc);status=409 if code=="stale_revision" else 422
            raise HTTPException(status,detail={"code":code,"currentRevision":len(record.graph.revisions)}) from exc
        application.modification_proposals[proposal.proposal_id]=proposal
        if body.operationId:application.modification_operations[body.operationId]=proposal
        events=application.repository.append_events(project_id,len(record.graph.revisions),[
            {"type":"modification.requested","semantic_ids":body.selectedSemanticIds,"payload":{"request":body.request}},
            {"type":"modification.preview_ready","semantic_ids":list(proposal.affected_ids),"payload":{"proposalId":proposal.proposal_id,"affected":list(proposal.affected_ids),"regenerated":list(proposal.regenerate),"unchanged":list(proposal.unaffected)}}])
        await application.publish_with_narration(events,record.graph,record.representations)
        return proposal.to_dict()

    @app.post("/api/projects/{project_id}/verification/{finding_id}/repair-proposal",status_code=201)
    async def repair_verification_finding(project_id:str,finding_id:str)->dict[str,Any]:
        record=_record(application,project_id); finding=record.graph.entities.get(finding_id)
        if finding is None or finding.kind is not EntityKind.VERIFICATION_RESULT: raise HTTPException(404,"Finding not found")
        if finding.verification_status!="failed" and finding.metadata.get("check")!="flyback": raise HTTPException(422,detail={"code":"finding_not_repairable"})
        check=finding.metadata.get("check"); targets=finding.metadata.get("semanticIds",finding.metadata.get("entity_ids",[]))
        driver="component-driver" if "component-driver" in record.graph.entities else next((x for x in targets if x in record.graph.entities),None)
        if check not in {"flyback","missing-driver","direct-pump-gpio"} or not driver: raise HTTPException(422,detail={"code":"no_bounded_repair"})
        proposal=propose(record.graph,len(record.graph.revisions),[driver],"Replace with a logic-level MOSFET and flyback protection","verification_repair")
        application.modification_proposals[proposal.proposal_id]=proposal
        events=application.repository.append_events(project_id,len(record.graph.revisions),[{"type":"modification.preview_ready",
            "semantic_ids":list(proposal.affected_ids),"payload":{"proposalId":proposal.proposal_id,"affected":list(proposal.affected_ids),
            "regenerated":list(proposal.regenerate),"unchanged":list(proposal.unaffected)}}])
        await application.publish_with_narration(events,record.graph,record.representations)
        return proposal.to_dict()

    @app.delete("/api/projects/{project_id}/modification-proposals/{proposal_id}")
    async def cancel_modification(project_id:str,proposal_id:str)->dict[str,bool]:
        proposal=application.modification_proposals.pop(proposal_id,None)
        if proposal:
            for event in application.repository.append_events(project_id,proposal.base_revision,[{"type":"modification.cancelled","semantic_ids":list(proposal.target_ids),"payload":{"proposalId":proposal_id}}]): await application.broker.publish_committed(event)
        return {"cancelled":bool(proposal)}

    @app.post("/api/projects/{project_id}/modification-proposals/{proposal_id}/commit")
    async def commit_modification(project_id:str,proposal_id:str,idempotency_key:Optional[str]=Header(None,alias="Idempotency-Key"))->dict[str,Any]:
        operation_id=idempotency_key or proposal_id
        previous=application.find_operation("modification.operation_completed",operation_id,project_id)
        if previous:return previous.payload["result"]
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
            response={"projectId":project_id,"revision":len(updated.revisions),"summary":proposal.summary,"diff":diff,"representations":reps}
            drafts=[{"type":"modification.committed","semantic_ids":list(proposal.affected_ids),"payload":{"proposalId":proposal_id,"diff":diff}},{"type":"revision.committed","semantic_ids":list(proposal.affected_ids),"payload":{"diff":diff}},*lifecycle,{"type":"modification.operation_completed","semantic_ids":list(proposal.affected_ids),"payload":{"operationId":operation_id,"result":response}}]
            verification={"outcome":proposal.verification,"diff":diff,"kind":"undo" if proposal.mode=="undo" else "modification"}
            committed=application.repository.save_commit(updated_record,result.patch,verification,drafts)
            await application.publish_with_narration(committed,updated,reps)
            application.modification_proposals.pop(proposal_id,None)
            return response
        finally:lock.release()

    @app.post("/api/projects/{project_id}/revisions/undo")
    async def undo_revision(project_id:str,idempotency_key:Optional[str]=Header(None,alias="Idempotency-Key"))->dict[str,Any]:
        operation_id=idempotency_key or f"undo-{project_id}-{len(_record(application,project_id).graph.revisions)}"
        previous=application.find_operation("undo.operation_completed",operation_id,project_id)
        if previous:return previous.payload["result"]
        record=_record(application,project_id)
        revisions=application.repository.list_revisions(project_id)
        source=revisions[-1] if revisions and revisions[-1].get("verification",{}).get("kind")=="modification" else None
        if source is None: raise HTTPException(409,detail={"code":"nothing_to_undo"})
        try: proposal=inverse_proposal(record.graph,source)
        except ValueError as exc: raise HTTPException(409,detail={"code":str(exc)}) from exc
        application.modification_proposals[proposal.proposal_id]=proposal
        result=await commit_modification(project_id,proposal.proposal_id,operation_id)
        events=application.repository.append_events(project_id,result["revision"],[{"type":"undo.operation_completed","semantic_ids":list(proposal.affected_ids),"payload":{"operationId":operation_id,"result":result}}])
        await application.publish_with_narration(events,_record(application,project_id).graph,result["representations"])
        return result

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
    parser.add_argument("--port", default=int(os.getenv("PORT", str(settings.workspace_port))), type=int)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args()
    if args.open_browser:
        webbrowser.open(f"http://{args.host}:{args.port}")
    import uvicorn
    uvicorn.run("aura.workspace.server:create_app", host=args.host, port=args.port, reload=False, factory=True)


if __name__ == "__main__":
    main()
