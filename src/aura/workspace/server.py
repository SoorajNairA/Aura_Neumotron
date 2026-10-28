from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import time
import webbrowser
import threading
import os
from collections import deque
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional, Union
from uuid import uuid4

from fastapi import Body, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation, apply_patch
from aura.capabilities import CAPABILITY_MANIFEST, classify_objective
from aura.engineering_graph.serialization import graph_from_dict, graph_to_dict
from aura.engineering_graph.serialization import patch_from_dict, patch_to_dict
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
from aura.verification.delta import verification_readiness
from .bridge import WorkspaceBridge
from .ideas import compose_objective, new_session, proposal_card, ready_to_propose, run_rules, run_turn, wants_breadboard
from .assessment import (
    REQUEST_SCOPE, PlanningOrigin, RepresentationInput, RequestAssessment, RequestLedger, WorkspaceAssessment, assess_request,
    assess_workspace, collect_request_obligations, refresh_assessment,
)
from .assembly import engineering_assembly
from .events import WorkspaceEvent
from .representation_service import RepresentationService, initial_records, representation_specs
from .representations import RepresentationRecord, RepresentationStatus, RepresentationType
from .modifications import LiveModificationPlanner,ModificationError,ModificationProposal,inverse_proposal,propose,propose_add_components,part_interfaces,propose_connection,propose_parameter_change,propose_pin_change
from .narration import NarrationService
from .project_package import EMPTY_LAYOUT, MAX_PACKAGE_BYTES, PackageContents, PackageError, build_zip, read_zip, rewrite_project_id, slug, validate_layout
from .work_items import EngineeringWorkService, WorkDomainError
from .scenarios import EngineeringScenario,LiveScenarioAnalyzer,ScenarioError,analyze as analyze_scenario
from aura.firmware import FirmwareUnsupported, generate_fan_sketch
from aura.firmware.sketch import extract_control, splice_control
from aura.firmware.compile import CompileResult, compile_sketch
from aura.firmware.generic import generate_generic_sketch
from aura.hardware.ports import list_ports
from aura.hardware.upload import upload_sketch
from aura.hardware.serial import SerialSession, evidence, fake_board
from aura.hardware.ports import FAKE_PORT, fake_enabled
from aura.firmware.compile import find_cli
from aura.firmware.io import RuleError, default_rules, io_points, validate_rules

LOGGER = logging.getLogger("aura.workspace")
MAX_PENDING_ENTRIES = 256


def _remember_bounded(store: dict[str, Any], key: str, value: Any, max_entries: int = MAX_PENDING_ENTRIES) -> None:
    store[key]=value
    while len(store)>max_entries:
        store.pop(next(iter(store)))


class IdeaBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idea: str = Field(min_length=3,max_length=2000)
    planningMode: Literal["deterministic_test","live_model"] = "live_model"


class IdeaMessageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1,max_length=2000)


class IdeaApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposalId: str = Field(min_length=1,max_length=128)
    breadboard: Optional[bool] = None


class CreateProjectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=8,max_length=2000)
    planningMode: Literal["deterministic_test","live_model"] = "deterministic_test"
    operationId: Optional[str] = Field(default=None,max_length=128)


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

class UploadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # A port name never starts with "-", so it cannot be read as an arduino-cli option.
    port: str = Field(min_length=1,max_length=64,pattern=r"^[A-Za-z0-9/][A-Za-z0-9_./-]*$")


class LayoutBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    layout: dict[str, Any]


class FirmwareEditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block: str = Field(min_length=1,max_length=20000)
    revisionId: str = Field(min_length=1,max_length=128)


class ParameterProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseRevision:int
    componentId:str
    key:str
    value:Union[bool,int,float,str]


class ConnectionProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseRevision:int
    sourceId:str
    sourceInterface:str
    targetId:str
    targetInterface:str


class ComponentProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseRevision:int
    componentDefinitionIds:list[str]


class PinProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseRevision: int
    controllerId: str = Field(min_length=1,max_length=128)
    port: str = Field(min_length=1,max_length=64)
    gpio: int


class ProposalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    projectId:str=Field(min_length=1,max_length=160);baseRevision:int=Field(ge=0);selectedSemanticIds:list[str]=Field(min_length=1,max_length=16);request:str=Field(min_length=5,max_length=2000);mode:Literal["automatic","parameter_change"]="automatic";operationId:Optional[str]=Field(default=None,max_length=128)

class WorkItemBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    title:str=Field(min_length=1,max_length=200);description:str=Field(default="",max_length=2000);category:str=Field(default="engineering",max_length=80)
    relatedComponentIds:list[str]=Field(default_factory=list,max_length=32);relatedRequirementIds:list[str]=Field(default_factory=list,max_length=32);relatedFindingIds:list[str]=Field(default_factory=list,max_length=32);source:str=Field(default="manual",max_length=80)

class WorkTransitionBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    targetState:str=Field(min_length=1,max_length=32);reason:Optional[str]=Field(default=None,max_length=1000);actor:Optional[str]=Field(default=None,max_length=100)

class WorkCommandBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    command:str=Field(min_length=3,max_length=2000);reason:Optional[str]=Field(default=None,max_length=1000);actor:Optional[str]=Field(default="AURA",max_length=100)

class ScenarioBody(BaseModel):
    model_config=ConfigDict(extra="forbid")
    targetSemanticId:str;changeType:Literal["REPLACE_COMPONENT","REMOVE_COMPONENT","MODIFY_PROPERTY"];value:Any=None


class EventBroker:
    def __init__(self, repository: ProjectRepository, listener_queue_size: int = 128, event_cache_size: int = 512) -> None:
        self.repository = repository
        self.listener_queue_size=listener_queue_size
        self.event_cache_size=event_cache_size
        self.events: dict[str, deque[EventEnvelope]] = {}
        self.listeners: dict[str, set[asyncio.Queue[EventEnvelope]]] = {}

    def reset(self, project_id: str) -> None:
        self.events[project_id] = deque(maxlen=self.event_cache_size)

    async def publish_committed(self, event: StoredEvent) -> EventEnvelope:
        envelope = EventEnvelope(eventId=event.event_id, projectId=event.project_id,
            revision=event.revision, type=event.type, semanticIds=event.semantic_ids,
            payload=event.payload, timestamp=event.timestamp)
        self.events.setdefault(event.project_id, deque(maxlen=self.event_cache_size)).append(envelope)
        for queue in tuple(self.listeners.get(event.project_id, set())):
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                self.listeners[event.project_id].discard(queue)
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
        self.idea_proposals:dict[str,tuple[str,str,PlanningOutcome]]={}
        self.modification_operations:dict[str,ModificationProposal]={}
        self.modification_locks:dict[str,list[Any]]={}
        self.modification_locks_guard=threading.Lock()
        self.creation_locks:dict[str,list[Any]]={}
        self.creation_locks_guard=threading.Lock()
        self.active_representation_operations:set[str]=set()
        self.work_service=EngineeringWorkService(self.repository)
        self.scenarios:dict[str,EngineeringScenario]={}
        # Set by create_app: (project_id, graph) -> the firmware source a download would use, or None when unsupported.
        self.firmware_source:Any=None

    def try_modification_lock(self, project_id: str) -> threading.Lock | None:
        with self.modification_locks_guard:
            entry=self.modification_locks.setdefault(project_id,[threading.Lock(),0])
            lock=entry[0]
            if not lock.acquire(blocking=False):
                return None
            entry[1]+=1
            return lock

    def release_modification_lock(self, project_id: str, lock: threading.Lock) -> None:
        with self.modification_locks_guard:
            entry=self.modification_locks.get(project_id)
            if entry is None or entry[0] is not lock:
                raise RuntimeError("modification lock ownership was lost")
            lock.release()
            entry[1]-=1
            if entry[1]==0:
                self.modification_locks.pop(project_id,None)

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
                if outcome.mode=="deterministic_fallback" and outcome.fallback_reason and any(term in outcome.fallback_reason for term in ("Application Default Credentials","ADC/IAM access","NEBIUS_API_KEY","API key was rejected")):
                    raise RuntimeError(outcome.fallback_reason)
                if outcome.mode == "deterministic_fallback" and not fallback_enabled:
                    raise RuntimeError(outcome.fallback_reason or "live planning failed")
                return outcome
            if not fallback_enabled:
                raise RuntimeError("live model is unavailable and deterministic fallback is disabled")
        mode = "deterministic_test" if body.planningMode == "deterministic_test" else "deterministic_fallback"
        reason = None if mode == "deterministic_test" else "live model was not configured"
        return PlanningOutcome(PlannerService().plan(request), mode, reason)

    def model_profiles(self) -> Any:
        if getattr(self, "_model_profiles", None) is None:
            from aura.app.config import aura_data_dir
            from aura.app.model_profiles import ProfileStore
            self._model_profiles = ProfileStore(aura_data_dir() / "model_profiles.json")
        return self._model_profiles

    def reset_default_provider(self) -> None:
        """Forget a provider built from configuration so the next call rebuilds it; an injected provider stays."""
        if self.provider is not None and self.provider is getattr(self, "_configured_provider", None):
            self.provider = None
        self._configured_provider = None

    def _default_provider(self) -> Any | None:
        provider = self._build_default_provider()
        self._configured_provider = provider
        return provider

    def _build_default_provider(self) -> Any | None:
        try:
            from aura.app.config import Settings
            settings = Settings()
            # A profile the user activated decides alone; if it fails the error surfaces and no other provider is tried.
            profiles = self.model_profiles()
            if profiles.active_id():
                return profiles.build_provider(timeout=settings.planner_timeout)
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
            if settings.planner_provider=="nebius":
                from aura.infrastructure.llm.nebius import NebiusPlannerProvider
                return NebiusPlannerProvider(settings.nebius_api_key,settings.nebius_base_url,settings.nebius_model,settings.planner_timeout)
            if settings.planner_provider=="deterministic":return None
            raise RuntimeError(f"Unsupported Planner provider: {settings.planner_provider}")
        except RuntimeError:raise
        except Exception as exc:raise RuntimeError(f"Could not initialize Planner provider: {exc}") from exc

    @staticmethod
    def _friendly_finding(finding: Any) -> str:
        check=str(getattr(finding,"check","")).lower()
        message=str(getattr(finding,"message","")).lower()
        if check in {"mech_301","mech_310"} or "mechanically connected" in message:
            return "Drive motor is not connected to the wheel or mechanism."
        if check=="direct-pump-gpio" or "directly from controller gpio" in message:
            return "Motor requires a driver between the controller and motor."
        if check in {"connection-endpoint","elec_411"} or "undefined interface" in message:
            return "A required component connection could not be resolved."
        if check in {"power-connection","common-ground"}:
            return "Required low-voltage power or ground connection is incomplete."
        if check.startswith("req_"):
            return "A required function of this design is still missing."
        return "A required engineering connection remains unresolved."

    def _store_build_incomplete(self, body: CreateProjectBody, outcome: PlanningOutcome, plan, verification, planner_metadata: dict[str, Any],
                                event_drafts: list[dict[str, Any]], repair_metadata: dict[str, Any]) -> StoredProject:
        """Persist only a safe diagnostic project, never the rejected graph."""
        project_id=plan.entities[0].id;now=datetime.now(timezone.utc).isoformat()
        ledger = collect_request_obligations(body.objective)
        user_issues=list(dict.fromkeys(self._friendly_finding(finding) for finding in verification.findings if finding.severity=="critical" and finding.state is VerificationState.FAILED))
        user_message="AURA couldn't resolve this engineering architecture reliably."
        project=EngineeringEntity(project_id,EntityKind.PROJECT,plan.request.project_name,metadata={"objective":body.objective,"generationStatus":"build_incomplete","userMessage":user_message,"userIssues":user_issues,
            "requestObligations":ledger.to_dict()["obligations"],"requestObjectiveDigest":ledger.objective_digest},verification_status=VerificationState.FAILED.value)
        findings=[EngineeringEntity(finding.id,EntityKind.VERIFICATION_RESULT,finding.message,project_id,
            finding.to_dict()|{"userMessage":self._friendly_finding(finding)},verification_status=finding.state.value) for finding in verification.findings]
        patch=GraphPatch(f"incomplete-{uuid4().hex}",tuple([GraphOperation(PatchOperation.ADD_ENTITY,entity=project),*[GraphOperation(PatchOperation.ADD_ENTITY,entity=finding) for finding in findings]]),"Record incomplete engineering build")
        graph=apply_patch(EngineeringGraph(project_id),patch)
        record=StoredProject(project_id,body.objective,outcome.mode,outcome.fallback_reason,"build_incomplete",graph,[],now,now)
        event_drafts.append({"type":"project.build_incomplete","semantic_ids":[project_id],"payload":{"status":"build_incomplete","message":user_message,"issues":user_issues}})
        if body.operationId:event_drafts.append({"type":"project.operation_completed","semantic_ids":[project_id],"payload":{"operationId":body.operationId,"projectId":project_id,"revision":len(graph.revisions)}})
        verification_payload={"state":verification.state.value,"decision":verification.decision.value,"reasons":list(verification.reasons),"findings":[finding.__dict__|{"state":finding.state.value,"userMessage":self._friendly_finding(finding)} for finding in verification.findings],"repair":repair_metadata}
        verification_payload["workspaceAssessment"] = self._creation_assessment(record, verification, planner_metadata).to_dict()
        committed=self.repository.save_commit(record,patch,verification_payload,event_drafts)
        self.broker.reset(project_id)
        return record

    def _creation_assessment(self, record: StoredProject, verification, planner_metadata: dict[str, Any], specs=()) -> WorkspaceAssessment:
        """Prepare revision metadata before the existing atomic project commit."""
        ledger = collect_request_obligations(record.objective)
        root = record.graph.get(record.project_id)
        if root.metadata.get("requestObjectiveDigest") != ledger.objective_digest or (
            root.metadata.get("requestObligations") != ledger.to_dict()["obligations"]
        ):
            raise ValueError("Creation assessment requires the original request ledger")
        return self._revision_assessment(record, verification, specs=specs,
            planning_origin=PlanningOrigin(provider=planner_metadata.get("provider"), model=planner_metadata.get("model"),
                planning_mode=record.planning_mode, reused_project=False, fallback_reason=record.fallback_reason,
                verification_status=verification.state.value))

    def _revision_assessment(self, record: StoredProject, verification, *, specs=None,
                             planning_origin: PlanningOrigin | None = None) -> WorkspaceAssessment:
        """Assess the supplied graph, retaining original ledger and creation limits."""
        previous = self.assessment(record) if planning_origin is None else None
        digest = hashlib.sha256(record.objective.encode("utf-8")).hexdigest()
        root = record.graph.entities.get(record.project_id)
        limitations = previous.limitations if previous is not None else ()
        try:
            ledger = RequestLedger.from_dict({"originalObjective": record.objective, "objectiveDigest": root.metadata["requestObjectiveDigest"],
                "obligations": root.metadata["requestObligations"], "evaluationScope": REQUEST_SCOPE})
            request = assess_request(ledger, record.graph)
        except (ValueError, TypeError, KeyError, AttributeError):
            request = RequestAssessment(original_objective_digest=digest,
                reasons=("Original request ledger is absent or invalid; original requirements were not reassessed",))
            limitations += request.reasons
        if specs is None:
            try: specs = representation_specs(record.graph)
            except (ValueError, TypeError, KeyError, OverflowError):
                specs = ()
                limitations += ("Representation classification is unavailable for this graph",)
        by_semantics = {(item.kind, item.semantic_ids): item for item in specs}
        records = tuple(RepresentationRecord.from_dict(item) for item in record.representations)
        result = assess_workspace(
            operational_status=record.status, assessed_revision_id=record.graph.current_revision_id,
            revision_number=len(record.graph.revisions), current_revision_id=record.graph.current_revision_id,
            current_revision_number=len(record.graph.revisions), request=request,
            verification=verification, check_coverage=verification.execution_coverage, original_objective_digest=digest,
            representations=tuple(RepresentationInput(item, by_semantics.get((item.type, item.semantic_ids))) for item in records),
            planning_origin=planning_origin if planning_origin is not None else previous.planning_origin,
        )
        limitations = (*limitations, *result.limitations, *verification.reasons, *(finding.message for finding in verification.findings
            if finding.severity == "warning" or finding.state in {
                VerificationState.CONCEPTUAL, VerificationState.ESTIMATED, VerificationState.UNSUPPORTED,
                VerificationState.STALE, VerificationState.FAILED,
            }))
        return replace(result, limitations=tuple(dict.fromkeys(limitations)))

    def assessment(self, record: StoredProject, *, reused_project: bool | None = None,
                   revision_number: int | None = None) -> WorkspaceAssessment:
        """One read-only assessment path for create, get, list and verification."""
        digest = hashlib.sha256(record.objective.encode("utf-8")).hexdigest()
        root = record.graph.entities.get(record.project_id)
        has_ledger = root is not None and isinstance(root.metadata.get("requestObligations"), list) and (
            root.metadata.get("requestObjectiveDigest") == digest
        )
        limitation = "No persisted revision assessment and original request ledger; request and check coverage are unknown"
        for row in reversed(self.repository.list_revisions(record.project_id)):
            if revision_number is not None and row["revision"] != revision_number:
                continue
            if has_ledger or row["verification"].get("workspaceAssessment") is not None:
                value = row["verification"].get("workspaceAssessment")
                if value is None:
                    continue
                try:
                    snapshot = WorkspaceAssessment.from_dict(value)
                    number = row["revision"]
                    if not (snapshot.assessed_revision_id == row["revisionId"] == record.graph.revisions[number - 1].id
                            and snapshot.revision_number == number and snapshot.original_objective_digest == digest
                            and snapshot.request.original_objective_digest == digest):
                        raise ValueError("Assessment does not match its committed revision or original objective")
                    return refresh_assessment(snapshot, operational_status=record.status,
                        current_revision_id=record.graph.current_revision_id, current_revision_number=len(record.graph.revisions),
                        representations=tuple(RepresentationRecord.from_dict(item) for item in record.representations),
                        reused_project=reused_project)
                except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                    limitation = "Persisted assessment is invalid or has an inconsistent revision binding; no read repair was performed"
                    break
        result = assess_workspace(operational_status=record.status, assessed_revision_id=None, revision_number=0,
            current_revision_id=record.graph.current_revision_id, current_revision_number=0,
            planning_origin=PlanningOrigin(planning_mode=record.planning_mode, reused_project=reused_project,
                fallback_reason=record.fallback_reason))
        return replace(result, limitations=result.limitations + (limitation,))

    def _operation_response(self, record: StoredProject, response: dict[str, Any]) -> dict[str, Any]:
        """A replay retains its operation revision and marks older proof stale."""
        return dict(response) | {"assessment": self.assessment(record, revision_number=response["revision"]).to_dict()}

    async def create(self, body: CreateProjectBody, *, creation_info: dict[str, Any] | None = None,
                     outcome: PlanningOutcome | None = None) -> StoredProject:
        key=PlannerService._id(body.objective,"project")
        with self.creation_locks_guard:
            entry=self.creation_locks.setdefault(key,[threading.Lock(),0])
            entry[1]+=1
        lock=entry[0]
        await run_in_threadpool(lock.acquire)
        try:
            # An approved idea proposal carries its already-reviewed plan; plain creates plan here.
            planned = {"planned": outcome} if outcome is not None else {}
            if creation_info is None:
                return await self._create_serialized(body, **planned)
            return await self._create_serialized(body, creation_info=creation_info, **planned)
        finally:
            lock.release()
            with self.creation_locks_guard:
                entry[1]-=1
                if entry[1]==0:self.creation_locks.pop(key,None)

    async def _resume_incomplete_representations(self, record: StoredProject) -> StoredProject:
        records=[RepresentationRecord.from_dict(value) for value in record.representations]
        retryable={RepresentationStatus.REQUESTED,RepresentationStatus.FAILED,RepresentationStatus.FALLBACK}
        if not any(item.status in retryable for item in records):
            return record
        specs={(spec.kind,spec.semantic_ids):spec for spec in representation_specs(record.graph)}
        completed=[];events=[]
        for item in records:
            spec=specs.get((item.type,item.semantic_ids))
            if item.status not in retryable or spec is None:
                completed.append(item)
                continue
            regenerated=(await run_in_threadpool(self.representation_service.persist_specs,record.project_id,
                len(record.graph.revisions),[item],[spec]))[0]
            completed.append(regenerated)
            events.append({"type":"representation.generating","semantic_ids":list(item.semantic_ids),
                "payload":{"representationId":item.representation_id,"retry":True}})
            if regenerated.status is RepresentationStatus.FALLBACK:
                events.append({"type":"representation.failed","semantic_ids":list(item.semantic_ids),
                    "payload":{"representationId":item.representation_id,"error":regenerated.error,"retry":True}})
            events.append({"type":f"representation.{regenerated.status.value}","semantic_ids":list(item.semantic_ids),
                "payload":{"representationId":item.representation_id,"artifactId":regenerated.artifact_id,"error":regenerated.error,"retry":True}})
        record.representations=[item.to_dict() for item in completed]
        record.status="build_incomplete" if any(item.status is not RepresentationStatus.READY for item in completed) else "ready_with_limitations"
        self.repository.update_representations(record.project_id,record.representations)
        self.repository.update_project_status(record.project_id,record.status)
        if events:
            committed=self.repository.append_events(record.project_id,len(record.graph.revisions),events)
            await self.publish_with_narration(committed,record.graph,record.representations)
        return record

    async def _create_serialized(self, body: CreateProjectBody, *, creation_info: dict[str, Any] | None = None,
                                 planned: PlanningOutcome | None = None) -> StoredProject:
        if creation_info is not None:
            creation_info["reusedProject"] = False
        if body.operationId:
            completed=self.find_operation("project.operation_completed",body.operationId)
            if completed:
                existing=self.repository.get_project(completed.payload["projectId"])
                if existing:
                    if creation_info is not None: creation_info["reusedProject"] = True
                    return existing
        existing=self.repository.get_project(PlannerService._id(body.objective,"project"))
        if existing is not None:
            if creation_info is not None: creation_info["reusedProject"] = True
            return await self._resume_incomplete_representations(self.recover_interrupted(existing))
        ledger = collect_request_obligations(body.objective)
        try:
            outcome = planned or await run_in_threadpool(self.plan, body)
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
        # Project IDs are objective-derived. Repeating the same create request is
        # idempotent in every planner mode, not only in deterministic tests.
        if existing is not None:
            if creation_info is not None: creation_info["reusedProject"] = True
            return await self._resume_incomplete_representations(self.recover_interrupted(existing))
        planner_metadata = dict(outcome.provider_metadata or {})
        planner_metadata.update({"provider": (self.provider.get_diagnostics().get("backend","live_model") if hasattr(self.provider,"get_diagnostics") else "live_model") if outcome.mode == "live_model" else "deterministic", "fallbackUsed": outcome.mode != "live_model", "planId": plan.patch.id, "componentCount": len(plan.components), "relationshipCount": len(plan.relationships)})
        event_drafts = [{"type": "project.started", "payload": {"planningMode": outcome.mode,"operationId":body.operationId,"planner":planner_metadata}, "semantic_ids": []}]
        if outcome.mode == "live_model":
            event_drafts.append({"type": "planning.live_model", "payload": {"message": "Planning with live model"}, "semantic_ids": []})
        elif outcome.mode == "deterministic_fallback":
            event_drafts.append({"type": "task.fallback_used", "payload": {"reason": outcome.fallback_reason}, "semantic_ids": []})
        verifier=VerificationService();verified = verifier.verify(plan)
        repair_metadata={"repairAttempted":False,"repairProvider":None,"repairLatencyMs":0.0,"verificationFindingsBefore":[],"verificationFindingsAfter":[],"repairSucceeded":False}
        if not verified.accepted:
            before=[finding.to_dict() for finding in verified.findings if finding.severity=="critical" and finding.state is VerificationState.FAILED]
            started=time.perf_counter()
            attempt=(LivePlanner(self.provider,self.planner_timeout).repair(plan,verified)
                     if outcome.mode=="live_model" and self.provider is not None
                     else PlannerService().repair(plan,verified))
            plan=attempt.plan
            project_id=plan.entities[0].id
            verified=verifier.verify(plan)
            after=[finding.to_dict() for finding in verified.findings if finding.severity=="critical" and finding.state is VerificationState.FAILED]
            repair_metadata=attempt.metadata|{"repairLatencyMs":round((time.perf_counter()-started)*1000,1),"verificationFindingsBefore":before,"verificationFindingsAfter":after,"repairSucceeded":verified.accepted,"repairContext":attempt.context}
            planner_metadata["repair"]=repair_metadata
            event_drafts.append({"type":"planning.repair_attempted","semantic_ids":[],"payload":{"repairAttempted":True,"findingCount":len(before)}})
            if not verified.accepted:
                incomplete=self._store_build_incomplete(body,outcome,plan,verified,planner_metadata,event_drafts,repair_metadata)
                await self.publish_with_narration(self.repository.get_events_after(incomplete.project_id,0),incomplete.graph,incomplete.representations)
                return incomplete
        # Add original-request metadata to the accepted initial patch, before its
        # first revision/transaction. Repair/provider text is never its authority.
        verified = replace(verified, patch=replace(verified.patch, operations=tuple(
            replace(operation, entity=replace(operation.entity, metadata=operation.entity.metadata | {
                "requestObligations": ledger.to_dict()["obligations"],
                "requestObjectiveDigest": ledger.objective_digest,
            })) if operation.entity is not None and operation.entity.id == project_id
                and operation.entity.kind is EntityKind.PROJECT else operation
            for operation in verified.patch.operations
        )))
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
        verification["workspaceAssessment"] = self._creation_assessment(record, verified, planner_metadata, specs).to_dict()
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
        primary_sources={part["semanticId"]:part.get("transformSource") for part in assembly.get("parts",()) if part["semanticId"] in set(assembly.get("primaryMechanismIds",()))}
        physical_complete=(bool(physical_ids) and physical_ids <= ready_physical and len(assembly.get("parts",())) >= len(physical_ids)
            and not assembly.get("unresolvedMechanicalRelations") and not assembly.get("unresolvedPrimaryMechanism")
            and all(source in {"MATE_SOLVED","FIXED_ROOT"} for source in primary_sources.values()))
        required_failed = any(item.status is RepresentationStatus.FALLBACK for item in completed) or not physical_complete or not circuit_fidelity or critical_semantic
        verification_limited=verified.state in {VerificationState.ESTIMATED,VerificationState.CONCEPTUAL,VerificationState.STALE,VerificationState.UNSUPPORTED} or any(item.severity=="warning" for item in verified.findings)
        record.status = "build_incomplete" if required_failed else ("ready_with_limitations" if capability == "SUPPORTED_WITH_LIMITATIONS" or verification_limited else "ready")
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

    async def restore(self, contents: PackageContents, origin: Literal["imported","copied"]) -> StoredProject:
        """Create a new project from validated package contents (shared by Import and Make a copy)."""
        old_id=contents.graph.project_id;new_id=f"project-{uuid4().hex}"
        try:
            graph=graph_from_dict(rewrite_project_id(graph_to_dict(contents.graph),old_id,new_id))
            verification=rewrite_project_id(contents.latest_verification,old_id,new_id) if contents.latest_verification is not None else {"kind":"restore"}
            if contents.latest_patch is not None:
                patch=patch_from_dict(rewrite_project_id(patch_to_dict(contents.latest_patch),old_id,new_id))
            else:
                patch=GraphPatch(graph.revisions[-1].patch_id,(GraphOperation(PatchOperation.ADD_ENTITY,entity=graph.get(new_id)),),f"Project {origin}")
            if contents.firmware_edit:
                try: splice_control(generate_fan_sketch(graph).source,contents.firmware_edit["block"])
                except (FirmwareUnsupported,ValueError) as exc: raise PackageError("CORRUPT_GRAPH","firmware/edit.json does not fit this design") from exc
            specs=[]
            if contents.had_representations:
                try: specs=representation_specs(graph)
                except (ValueError,TypeError,KeyError,OverflowError): specs=[]
        except PackageError: raise
        except (ValueError,TypeError,KeyError,RecursionError) as exc: raise PackageError("CORRUPT_GRAPH",f"The project could not be restored: {str(exc)[:120]}") from exc
        now=datetime.now(timezone.utc).isoformat()
        representations=initial_records(new_id,len(graph.revisions),specs)
        record=StoredProject(new_id,contents.objective,contents.planning_mode,contents.fallback_reason,"building",graph,
            [item.to_dict() for item in representations],now,now)
        source=contents.manifest.get("projectId")
        provenance={"origin":origin,"sourceProjectId":source if isinstance(source,str) and len(source)<=128 else None,"exportedAt":str(contents.manifest.get("exportedAt",""))[:64]}
        drafts=[{"type":f"project.{origin}","semantic_ids":[new_id],"payload":provenance}]
        try:
            committed=self.repository.save_commit(record,patch,verification,drafts)
        except PersistenceFailure as exc:
            raise HTTPException(503,detail={"code":"persistence_failure","message":str(exc)}) from exc
        if contents.layout is not None: self.repository.save_layout(new_id,contents.layout)
        if contents.control_rules is not None: self.repository.save_control_rules(new_id,contents.control_rules)
        if contents.hardware_evidence is not None: self.repository.save_hardware_evidence(new_id,contents.hardware_evidence)
        if contents.firmware_edit: self.repository.save_firmware_edit(new_id,contents.firmware_edit["block"],contents.firmware_edit["revisionId"])
        self.broker.reset(new_id)
        await self.publish_with_narration(committed,graph,record.representations)
        completed=await run_in_threadpool(self.representation_service.persist_specs,new_id,len(graph.revisions),representations,specs)
        record.representations=[item.to_dict() for item in completed]
        self.repository.update_representations(new_id,record.representations)
        failed=any(item.status is not RepresentationStatus.READY for item in completed)
        record.status="build_incomplete" if failed else (contents.status if contents.status in {"ready","ready_with_limitations","build_incomplete"} else "ready_with_limitations")
        self.repository.update_project_status(new_id,record.status)
        events=[{"type":"representation.requested","semantic_ids":list(item.semantic_ids),"payload":{"representationId":item.representation_id,"type":item.type.value}} for item in completed]
        events+=[{"type":f"representation.{item.status.value}","semantic_ids":list(item.semantic_ids),"payload":{"representationId":item.representation_id,"artifactId":item.artifact_id,"error":item.error}}
            for item in completed if item.type.value=="circuit_schematic"]
        events.append({"type":"project.build_incomplete" if record.status=="build_incomplete" else "project.ready","semantic_ids":[new_id],"payload":{"status":record.status,"origin":origin}})
        await self.publish_with_narration(self.repository.append_events(new_id,len(graph.revisions),events),graph,record.representations)
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
        indexed=getattr(self.repository,"find_operation_event",None)
        if indexed is not None:
            return indexed(event_type,operation_id,project_id)
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
        exact = VerificationService().verify_graph(updated)
        assessment = self._revision_assessment(updated_record, exact)
        verification["workspaceAssessment"] = assessment.to_dict()
        try:
            committed = self.repository.save_commit(updated_record, result.patch, verification, event_drafts)  # type: ignore[arg-type]
        except PersistenceFailure as exc:
            raise HTTPException(503, detail={"code": "persistence_failure", "message": str(exc)}) from exc
        await self.publish_with_narration(committed,updated,representations)
        after_entity = updated.get(selected.id)
        after = {"id": after_entity.id, "name": after_entity.name, "revision": len(updated.revisions)}
        return {"projectId": project_id, "before": before, "after": after,
                "summary": patch.summary, "rerunChecks": [finding.check for finding in result.findings],
                "assessment": assessment.to_dict()}


def _added_without_driver(graph:Any)->list[dict[str,Any]]:
    """Library-added parts wired to a controller pin; firmware has no generated driver for them."""
    pins={c.id:c.metadata.get("parameters",{}).get("gpio_map") or {} for c in graph.find(kind=EntityKind.COMPONENT)}
    result=[]
    for wire in graph.find(kind=EntityKind.CONNECTION):
        m=wire.metadata;ends=((m.get("source_id"),m.get("source_interface"),m.get("target_id")),(m.get("target_id"),m.get("target_interface"),m.get("source_id")))
        for controller,port,part in ends:
            if str(part).startswith("component-user-") and port in pins.get(controller,{}) and part in graph.entities:
                result.append({"semanticId":part,"name":graph.get(part).name,"port":port,"gpio":pins[controller][port]})
    return result


def create_app(provider: Any | None = None, planner_timeout: float | None = None,
               repository: ProjectRepository | None = None, storage_mode: str | None = None,
               db_path: str | Path | None = None, artifact_dir: Path | None = None) -> FastAPI:
    application = WorkspaceApplication(provider, planner_timeout, repository, storage_mode, db_path, artifact_dir)
    app = FastAPI(title="AURA Engineering Workspace", version="0.2.0")
    app.state.workspace = application
    web_root = Path(__file__).with_name("web")
    app.mount("/assets/representation",StaticFiles(directory=web_root/"representation"),name="workspace-assets")

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
        creation_info: dict[str, Any] = {}
        record = await application.create(body, creation_info=creation_info)
        return _project_payload(record, assessment=application.assessment(record, reused_project=creation_info.get("reusedProject")))

    @app.get("/api/projects")
    def list_projects() -> list[dict[str, Any]]:
        return [_project_payload(record, concise=True, assessment=application.assessment(record))
                for record in application.repository.list_projects()]

    @app.get("/api/capabilities")
    def get_capabilities()->dict[str,Any]: return CAPABILITY_MANIFEST

    # --- Model profiles: keys are write-only and never appear in any response ---
    from aura.app.model_profiles import ProfileError
    def _profiles_payload()->dict[str,Any]:
        from aura.app.config import Settings
        store=application.model_profiles();active=store.active_id()
        return {"active":active,"activeSource":"profile" if active else "environment","environmentProvider":Settings().planner_provider,"profiles":store.list()}

    def _profile_http_error(exc:Exception)->HTTPException:
        return HTTPException(getattr(exc,"status",500),detail={"code":getattr(exc,"code","PROFILE_ERROR"),"message":getattr(exc,"message","Model profile request failed"),"errors":getattr(exc,"errors",[])})

    @app.get("/api/model-profiles")
    def list_model_profiles()->dict[str,Any]:
        try: return _profiles_payload()
        except ProfileError as exc: raise _profile_http_error(exc) from None

    @app.post("/api/model-profiles/active")
    def set_active_model_profile(body:dict[str,Any]=Body(...))->dict[str,Any]:
        try:
            application.model_profiles().set_active(str(body.get("profileId") or ""))
            application.reset_default_provider()
            return _profiles_payload()
        except ProfileError as exc: raise _profile_http_error(exc) from None

    @app.put("/api/model-profiles/{profile_id}")
    def put_model_profile(profile_id:str,body:dict[str,Any]=Body(...))->dict[str,Any]:
        try:
            if body.get("profileId") not in (None,profile_id): raise ProfileError("PROFILE_INVALID","profileId in the body must match the URL",["profileId mismatch"])
            profile=application.model_profiles().upsert({**body,"profileId":profile_id})
            application.reset_default_provider()
            return profile
        except ProfileError as exc: raise _profile_http_error(exc) from None

    @app.put("/api/model-profiles/{profile_id}/key",status_code=204)
    async def put_model_profile_key(profile_id:str,request:Request)->Response:
        # Raw body parsing: a framework validation error would echo the submitted value, which here is a secret.
        try:
            body=await request.json();key=body.get("key") if isinstance(body,dict) else None
            if not isinstance(key,str): raise ProfileError("PROFILE_INVALID","A key string is required",["key is required"])
            application.model_profiles().set_key(profile_id,key);application.reset_default_provider()
        except ValueError: raise HTTPException(422,detail={"code":"PROFILE_INVALID","message":"Body must be JSON with a key string","errors":["key is required"]}) from None
        except ProfileError as exc: raise _profile_http_error(exc) from None
        return Response(status_code=204)

    @app.delete("/api/model-profiles/{profile_id}",status_code=204)
    def delete_model_profile(profile_id:str)->Response:
        try: application.model_profiles().delete(profile_id);application.reset_default_provider()
        except ProfileError as exc: raise _profile_http_error(exc) from None
        return Response(status_code=204)

    @app.post("/api/model-profiles/{profile_id}/test")
    async def test_model_profile(profile_id:str)->dict[str,Any]:
        try: application.model_profiles().get(profile_id)
        except ProfileError as exc: raise _profile_http_error(exc) from None
        return await run_in_threadpool(application.model_profiles().test,profile_id)

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

    def _package_http(exc: PackageError, status: int = 400) -> HTTPException:
        return HTTPException(status, detail=exc.to_dict())

    @app.post("/api/projects/import", status_code=201)
    async def import_project(request: Request) -> dict[str, Any]:
        too_large = PackageError("TOO_LARGE", "Project file is larger than the 20 MB limit")
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_PACKAGE_BYTES:
            raise _package_http(too_large)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_PACKAGE_BYTES:
                raise _package_http(too_large)
        try:
            contents = await run_in_threadpool(read_zip, bytes(body))
            record = await application.restore(contents, "imported")
        except PackageError as exc:
            raise _package_http(exc) from exc
        return _project_payload(record, assessment=application.assessment(record))

    @app.get("/api/projects/{project_id}/layout")
    def get_layout(project_id: str) -> dict[str, Any]:
        _record(application, project_id)
        stored = application.repository.get_layout(project_id)
        return {"layout": validate_layout(stored["layout"]) if stored else json.loads(json.dumps(EMPTY_LAYOUT)),
                "updatedAt": stored["updatedAt"] if stored else None}

    @app.put("/api/projects/{project_id}/layout")
    def put_layout(project_id: str, body: LayoutBody) -> dict[str, Any]:
        _record(application, project_id)
        try: layout = validate_layout(body.layout)
        except PackageError as exc: raise _package_http(exc, 422) from exc
        return {"updatedAt": application.repository.save_layout(project_id, layout)}

    @app.get("/api/projects/{project_id}/export")
    def export_project(project_id: str) -> Response:
        record = _record(application, project_id)
        root = record.graph.entities.get(record.graph.project_id)
        data = build_zip(application, project_id)
        return Response(data, media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="aura-{slug(root.name if root else "")}.zip"'})

    @app.post("/api/projects/{project_id}/copy", status_code=201)
    async def copy_project(project_id: str) -> dict[str, Any]:
        _record(application, project_id)
        try:
            contents = await run_in_threadpool(lambda: read_zip(build_zip(application, project_id)))
            record = await application.restore(contents, "copied")
        except PackageError as exc:
            raise _package_http(exc) from exc
        return _project_payload(record, assessment=application.assessment(record))

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        record = _record(application, project_id)
        assessment = application.assessment(record)
        # Legacy reads must not silently migrate data or recover artifacts by writing.
        if assessment.assessed_revision_id is not None:
            record = application.recover_interrupted(record)
            assessment = refresh_assessment(assessment, operational_status=record.status,
                current_revision_id=record.graph.current_revision_id, current_revision_number=len(record.graph.revisions),
                representations=tuple(RepresentationRecord.from_dict(item) for item in record.representations))
        return _project_payload(record, assessment=assessment)

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
        record=_record(application,project_id)
        graph=record.graph
        findings=graph.find(kind=EntityKind.VERIFICATION_RESULT); evidence=graph.find(kind=EntityKind.EVIDENCE)
        statuses=[x.value for x in VerificationState]
        return {"projectId":project_id,"revision":len(graph.revisions),
                "summary":{status:sum(x.verification_status==status for x in findings) for status in statuses},
                "findings":[x.metadata for x in findings],"evidence":[x.metadata for x in evidence],
                "assessment":application.assessment(record).to_dict()}

    @app.get("/api/projects/{project_id}/evidence/{evidence_id}")
    def get_evidence(project_id: str,evidence_id: str) -> dict[str, Any]:
        graph=_record(application,project_id).graph
        item=graph.entities.get(evidence_id)
        if item is None or item.kind is not EntityKind.EVIDENCE: raise HTTPException(404,"Evidence not found")
        return item.metadata

    @app.get("/api/projects/{project_id}/revisions")
    def get_revisions(project_id: str) -> list[dict[str, Any]]:
        record = _record(application, project_id)
        return [{"revision": item["revision"], "revisionId": item["revisionId"],
                 "patchId": item["patch"].id, "summary": item["patch"].summary,
                 "verification": item["verification"] | ({"workspaceAssessment": application.assessment(
                     record, revision_number=item["revision"]).to_dict()} if "workspaceAssessment" in item["verification"] else {}),
                 "createdAt": item["createdAt"]}
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
            if prior:return application._operation_response(record, prior.payload["result"])
        try: current=next(RepresentationRecord.from_dict(x) for x in record.representations if x["representationId"]==representation_id)
        except StopIteration as exc:raise HTTPException(404,"Representation not found") from exc
        if current.revision!=len(record.graph.revisions):raise HTTPException(409,detail={"code":"stale_representation_revision"})
        updated=await run_in_threadpool(application.representation_service.regenerate,record.graph,current)
        record.representations=[updated.to_dict() if x["representationId"]==representation_id else x for x in record.representations]
        application.repository.update_representations(project_id,record.representations)
        result=updated.to_dict() | {"assessment": application.assessment(record).to_dict()};drafts=[{"type":f"representation.{updated.status.value}","semantic_ids":list(updated.semantic_ids),"payload":{"representationId":representation_id,"operationId":updated.operation_id}}]
        if idempotency_key:drafts.append({"type":"representation.operation_completed","semantic_ids":list(updated.semantic_ids),"payload":{"operationId":idempotency_key,"result":result}})
        events=application.repository.append_events(project_id,len(record.graph.revisions),drafts);await application.publish_with_narration(events,record.graph,record.representations)
        return result

    @app.post("/api/projects/{project_id}/modification-proposals",status_code=201)
    async def create_modification_proposal(project_id:str,body:ProposalBody)->dict[str,Any]:
        record=_record(application,project_id)
        if body.projectId!=project_id: raise HTTPException(422,"Project ID mismatch")
        if body.operationId and body.operationId in application.modification_operations:return application.modification_operations[body.operationId].to_dict()
        try:
            # deterministic_test is an explicit test harness. User-facing edits
            # require structured model intent and never fall back to phrase rules.
            if record.planning_mode=="deterministic_test":
                proposal=propose(record.graph,body.baseRevision,body.selectedSemanticIds,body.request,body.mode)
            else:
                provider=application.provider or application._default_provider()
                if provider is None or not hasattr(provider,"generate_structured"):
                    raise ModificationError("MODIFICATION_AI_UNAVAILABLE","Editing requires a configured structured AI provider.",503)
                application.provider=provider
                proposal=await run_in_threadpool(LiveModificationPlanner(provider).propose,record.graph,body.baseRevision,body.selectedSemanticIds,body.request,body.mode)
        except ModificationError as exc:
            raise HTTPException(exc.status,detail={"code":exc.code,"message":exc.message,"currentRevision":len(record.graph.revisions)}) from exc
        except ValueError as exc:
            code=str(exc);status=409 if code=="stale_revision" else 422
            raise HTTPException(status,detail={"code":code,"message":"That edit is not supported by the deterministic test harness.","currentRevision":len(record.graph.revisions)}) from exc
        except Exception as model_exc:
            error_name=model_exc.__class__.__name__
            if error_name=="VertexAuthenticationError":status,code=503,"MODIFICATION_AI_AUTHENTICATION"
            elif error_name=="VertexTimeoutError":status,code=504,"MODIFICATION_AI_TIMEOUT"
            else:status,code=502,"MODIFICATION_AI_UNAVAILABLE"
            raise HTTPException(status,detail={"code":code,"message":str(model_exc)}) from model_exc
        _remember_bounded(application.modification_proposals,proposal.proposal_id,proposal)
        if body.operationId:_remember_bounded(application.modification_operations,body.operationId,proposal)
        events=application.repository.append_events(project_id,len(record.graph.revisions),[
            {"type":"modification.requested","semantic_ids":body.selectedSemanticIds,"payload":{"request":body.request}},
            {"type":"modification.preview_ready","semantic_ids":list(proposal.affected_ids),"payload":{"proposalId":proposal.proposal_id,"affected":list(proposal.affected_ids),"regenerated":list(proposal.regenerate),"unchanged":list(proposal.unaffected)}}])
        await application.publish_with_narration(events,record.graph,record.representations)
        return proposal.to_dict()

    @app.post("/api/projects/{project_id}/component-proposals")
    def create_component_proposal(project_id:str,body:ComponentProposalBody)->dict[str,Any]:
        record=_record(application,project_id)
        try: proposal=propose_add_components(record.graph,body.baseRevision,body.componentDefinitionIds)
        except ModificationError as exc:
            raise HTTPException(exc.status,detail={"code":exc.code,"message":exc.message,"currentRevision":len(record.graph.revisions)}) from exc
        except ValueError as exc:
            raise HTTPException(409,detail={"code":str(exc),"currentRevision":len(record.graph.revisions)}) from exc
        _remember_bounded(application.modification_proposals,proposal.proposal_id,proposal)
        return proposal.to_dict()

    @app.post("/api/projects/{project_id}/parameter-proposals")
    def create_parameter_proposal(project_id:str,body:ParameterProposalBody)->dict[str,Any]:
        record=_record(application,project_id)
        try: proposal=propose_parameter_change(record.graph,body.baseRevision,body.componentId,body.key,body.value)
        except ModificationError as exc:
            raise HTTPException(exc.status,detail={"code":exc.code,"message":exc.message,"currentRevision":len(record.graph.revisions)}) from exc
        except ValueError as exc:
            raise HTTPException(409,detail={"code":str(exc),"currentRevision":len(record.graph.revisions)}) from exc
        _remember_bounded(application.modification_proposals,proposal.proposal_id,proposal)
        return proposal.to_dict()

    @app.get("/api/projects/{project_id}/components/{component_id}/interfaces")
    def get_part_interfaces(project_id:str,component_id:str)->list[dict[str,Any]]:
        try: return part_interfaces(_record(application,project_id).graph,component_id)
        except ModificationError as exc: raise HTTPException(exc.status,detail={"code":exc.code,"message":exc.message}) from exc

    @app.post("/api/projects/{project_id}/connection-proposals")
    def create_connection_proposal(project_id:str,body:ConnectionProposalBody)->dict[str,Any]:
        record=_record(application,project_id)
        try: proposal=propose_connection(record.graph,body.baseRevision,body.sourceId,body.sourceInterface,body.targetId,body.targetInterface)
        except ModificationError as exc:
            raise HTTPException(exc.status,detail={"code":exc.code,"message":exc.message,"currentRevision":len(record.graph.revisions)}) from exc
        except ValueError as exc:
            raise HTTPException(409,detail={"code":str(exc),"currentRevision":len(record.graph.revisions)}) from exc
        _remember_bounded(application.modification_proposals,proposal.proposal_id,proposal)
        return proposal.to_dict()

    @app.post("/api/projects/{project_id}/pin-proposals")
    def create_pin_proposal(project_id:str,body:PinProposalBody)->dict[str,Any]:
        record=_record(application,project_id)
        try: proposal=propose_pin_change(record.graph,body.baseRevision,body.controllerId,body.port,body.gpio)
        except ModificationError as exc:
            raise HTTPException(exc.status,detail={"code":exc.code,"message":exc.message,"currentRevision":len(record.graph.revisions)}) from exc
        except ValueError as exc:
            raise HTTPException(409,detail={"code":str(exc),"currentRevision":len(record.graph.revisions)}) from exc
        # Committed through the shared commit route, so revisions, verification and undo stay one path.
        _remember_bounded(application.modification_proposals,proposal.proposal_id,proposal)
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
        _remember_bounded(application.modification_proposals,proposal.proposal_id,proposal)
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
        if previous:return application._operation_response(_record(application, project_id), previous.payload["result"])
        proposal=application.modification_proposals.get(proposal_id)
        if not proposal: raise HTTPException(404,"Proposal not found")
        lock=application.try_modification_lock(project_id)
        if lock is None: raise HTTPException(409,detail={"code":"modification_in_progress"})
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
            readiness_status={"BUILD_INCOMPLETE":"build_incomplete","SUPPORTED_WITH_LIMITATIONS":"ready_with_limitations","SUPPORTED":"ready"}[verification_readiness(result)]
            updated_record=StoredProject(record.project_id,record.objective,record.planning_mode,record.fallback_reason,readiness_status,updated,reps,record.created_at,datetime.now(timezone.utc).isoformat())
            exact = VerificationService().verify_graph(updated)
            assessment = application._revision_assessment(updated_record, exact)
            diff={"changed":list(proposal.operations),"regenerated":list(proposal.regenerate),"affected":list(proposal.affected_ids),"unchanged":list(proposal.unaffected)}
            response={"projectId":project_id,"revision":len(updated.revisions),"summary":proposal.summary,"diff":diff,"representations":reps,"status":readiness_status,"verificationDelta":result.verification_delta,"assessment":assessment.to_dict()}
            drafts=[{"type":"modification.committed","semantic_ids":list(proposal.affected_ids),"payload":{"proposalId":proposal_id,"diff":diff}},{"type":"revision.committed","semantic_ids":list(proposal.affected_ids),"payload":{"diff":diff}},*lifecycle,{"type":"modification.operation_completed","semantic_ids":list(proposal.affected_ids),"payload":{"operationId":operation_id,"result":response}}]
            verification={"outcome":proposal.verification,"diff":diff,"verificationDelta":result.verification_delta,"kind":"undo" if proposal.mode=="undo" else "modification"}
            verification["workspaceAssessment"] = assessment.to_dict()
            committed=application.repository.save_commit(updated_record,result.patch,verification,drafts)
            await application.publish_with_narration(committed,updated,reps)
            application.modification_proposals.pop(proposal_id,None)
            return response
        finally:
            application.release_modification_lock(project_id,lock)

    @app.post("/api/projects/{project_id}/revisions/undo")
    async def undo_revision(project_id:str,idempotency_key:Optional[str]=Header(None,alias="Idempotency-Key"))->dict[str,Any]:
        operation_id=idempotency_key or f"undo-{project_id}-{len(_record(application,project_id).graph.revisions)}"
        previous=application.find_operation("undo.operation_completed",operation_id,project_id)
        if previous:return application._operation_response(_record(application, project_id), previous.payload["result"])
        record=_record(application,project_id)
        revisions=application.repository.list_revisions(project_id)
        source=revisions[-1] if revisions and revisions[-1].get("verification",{}).get("kind")=="modification" else None
        if source is None: raise HTTPException(409,detail={"code":"nothing_to_undo"})
        try: proposal=inverse_proposal(record.graph,source)
        except ValueError as exc: raise HTTPException(409,detail={"code":str(exc)}) from exc
        _remember_bounded(application.modification_proposals,proposal.proposal_id,proposal)
        result=await commit_modification(project_id,proposal.proposal_id,operation_id)
        events=application.repository.append_events(project_id,result["revision"],[{"type":"undo.operation_completed","semantic_ids":list(proposal.affected_ids),"payload":{"operationId":operation_id,"result":result}}])
        await application.publish_with_narration(events,_record(application,project_id).graph,result["representations"])
        return result

    def work_error(exc:WorkDomainError): raise HTTPException(exc.status,detail=exc.to_dict()) from exc

    # Firmware is generated on demand from the current revision; only the latest compile result is kept.
    firmware_compiles:dict[str,CompileResult]={}
    firmware_compiling:set[str]=set()

    def _effective_firmware(project_id:str,graph:EngineeringGraph)->tuple[Any,dict[str,Any]]:
        # Fan workflow first (with the user's saved fanControl block); any other design gets driver code plus its rule list.
        try: artifact=generate_fan_sketch(graph)
        except FirmwareUnsupported:
            ios=io_points(graph);stored=application.repository.get_control_rules(project_id)
            if stored is None: rules,dropped,meta=default_rules(ios),[],{"rulesSource":"default","explanation":"Default rule — not generated by the live model"}
            else:
                rules,dropped=[],[]
                bound=stored.get("bindings") or {};current={io.id:io.component_id for io in ios}
                for rule in stored.get("rules",[]):
                    # Rules naming parts that left or were replaced in the design are dropped and listed, never silently kept.
                    moved=any(rule.get(end) in bound and bound[rule.get(end)]!=current.get(rule.get(end)) for end in ("input","output"))
                    try:
                        if moved: raise RuleError("UNKNOWN_IO","part replaced")
                        rules+=validate_rules({"rules":[rule]},ios)
                    except RuleError: dropped.append(rule)
                meta={"rulesSource":stored.get("source","default"),"explanation":stored.get("explanation","")}
            return generate_generic_sketch(graph,rules),meta|{"droppedRules":dropped}
        edit=application.repository.get_firmware_edit(project_id)
        if not edit: return artifact,{}
        # An edited sketch reports its own revision, so a board still running the unedited code never counts as this one.
        board=_board_revision(graph.current_revision_id,edit)
        source=splice_control(artifact.source,edit["block"]).replace(f'REVISION_ID = "{graph.current_revision_id}"',f'REVISION_ID = "{board}"')
        return replace(artifact,source=source,revision_id=board),{}

    def _firmware_source(project_id:str,graph:EngineeringGraph)->str|None:
        try: return _effective_firmware(project_id,graph)[0].source
        except FirmwareUnsupported: return None
    application.firmware_source=_firmware_source

    @app.get("/api/hardware/ports")
    async def hardware_ports()->dict[str,Any]: return await run_in_threadpool(list_ports)

    def _board_revision(revision_id:str|None,edit:dict[str,Any]|None)->str|None:
        return f"{revision_id}+edit-{hashlib.sha256(edit['block'].encode()).hexdigest()[:6]}" if edit and revision_id else revision_id

    def _expected_board_revision(project_id:str,graph:EngineeringGraph)->str|None:
        try: artifact,_=_effective_firmware(project_id,graph);return artifact.revision_id
        except FirmwareUnsupported: return graph.current_revision_id

    @app.get("/api/projects/{project_id}/firmware")
    def get_firmware(project_id:str)->dict[str,Any]:
        graph=_record(application,project_id).graph;last=firmware_compiles.get(project_id)
        common={"hardwareEvidence":application.repository.get_hardware_evidence(project_id),"boardRevision":_expected_board_revision(project_id,graph),"revisionId":graph.current_revision_id,"lastCompile":last.to_dict() if last else None,
                "lastCompileCurrent":bool(last and last.revision_id==graph.current_revision_id),"addedWithoutDriver":_added_without_driver(graph)}
        try: artifact,meta=_effective_firmware(project_id,graph)
        except FirmwareUnsupported as exc: return {"supported":False,"reasons":list(exc.reasons),"edit":None,**common}
        if artifact.kind=="generic":
            return {"supported":True,"reasons":[],"kind":"generic","source":artifact.source,"pins":artifact.pins,"fqbn":artifact.fqbn,"libraries":list(artifact.libraries),
                    "ios":[asdict(io) for io in artifact.ios],"rules":list(artifact.rules),"edit":None,**meta,**common}
        edit=application.repository.get_firmware_edit(project_id)
        return {"supported":True,"reasons":[],"kind":"fan","source":artifact.source,"controlBlock":extract_control(artifact.source),"pins":artifact.pins,"fqbn":artifact.fqbn,
                "libraries":list(artifact.libraries),"tOnC":artifact.t_on_c,"tOffC":artifact.t_off_c,
                "edit":{"revisionId":edit["revisionId"],"needsReview":edit["revisionId"]!=graph.current_revision_id} if edit else None,**common}

    @app.put("/api/projects/{project_id}/firmware/edit")
    def save_firmware_edit(project_id:str,body:FirmwareEditBody)->dict[str,Any]:
        graph=_record(application,project_id).graph
        if body.revisionId!=graph.current_revision_id: raise HTTPException(409,detail={"code":"stale_revision","currentRevisionId":graph.current_revision_id})
        try: splice_control(generate_fan_sketch(graph).source,body.block)
        except FirmwareUnsupported as exc: raise HTTPException(422,detail={"code":"FIRMWARE_UNSUPPORTED","reasons":list(exc.reasons)}) from exc
        except ValueError as exc: raise HTTPException(422,detail={"code":str(exc),"message":"Edit only the fanControl function; keep its signature and leave the markers out."}) from exc
        application.repository.save_firmware_edit(project_id,body.block,graph.current_revision_id)
        firmware_compiles.pop(project_id,None)
        return {"revisionId":graph.current_revision_id,"saved":True}

    @app.delete("/api/projects/{project_id}/firmware/edit",status_code=204)
    def reset_firmware_edit(project_id:str)->Response:
        _record(application,project_id);application.repository.delete_firmware_edit(project_id);firmware_compiles.pop(project_id,None)
        return Response(status_code=204)

    # Ports held by a running serial monitor (port -> project id); upload refuses them instead of racing.
    busy_ports:dict[str,str]={};app.state.hardware_busy_ports=busy_ports
    uploading:set[str]=set();uploading_ports:dict[str,str]={};app.state.hardware_uploading_ports=uploading_ports
    serial_sessions:dict[str,SerialSession]={};app.state.serial_sessions=serial_sessions
    serial_locks:dict[str,asyncio.Lock]={}

    def _monitor_owner(port:str)->str|None:
        # A monitor whose process already exited (unplugged, bad port) no longer holds the port.
        owner=busy_ports.get(port);session=serial_sessions.get(owner) if owner else None
        if owner and (session is None or not session.running):
            busy_ports.pop(port,None);owner=None
        return owner

    @app.post("/api/projects/{project_id}/firmware/upload")
    async def upload_firmware(project_id:str,body:UploadBody)->dict[str,Any]:
        graph=_record(application,project_id).graph;last=firmware_compiles.get(project_id)
        try: artifact,_=_effective_firmware(project_id,graph)
        except FirmwareUnsupported as exc: raise HTTPException(422,detail={"code":"FIRMWARE_UNSUPPORTED","reasons":list(exc.reasons)}) from exc
        if last is None or last.status!="passed" or last.revision_id!=graph.current_revision_id:
            raise HTTPException(409,detail={"code":"COMPILE_REQUIRED","message":"Compile this revision first."})
        if project_id in uploading: raise HTTPException(409,detail={"code":"UPLOAD_IN_PROGRESS"})
        if _monitor_owner(body.port): raise HTTPException(409,detail={"code":"PORT_BUSY","message":"Stop the serial monitor on this port first."})
        if body.port in uploading_ports: raise HTTPException(409,detail={"code":"PORT_BUSY","message":"Another upload is using this port."})
        uploading.add(project_id);uploading_ports[body.port]=project_id
        try: result=await run_in_threadpool(upload_sketch,artifact,body.port)
        finally: uploading.discard(project_id);uploading_ports.pop(body.port,None)
        return result.to_dict()

    def _stop_serial(project_id:str)->None:
        session=serial_sessions.pop(project_id,None)
        if session is None: return
        session.stop()
        if busy_ports.get(session.port)==project_id: busy_ports.pop(session.port,None)

    @app.post("/api/projects/{project_id}/serial/start")
    async def serial_start(project_id:str,body:UploadBody)->dict[str,Any]:
        # Serialized per project: concurrent starts can never both register, so no monitor outlives its session.
        async with serial_locks.setdefault(project_id,asyncio.Lock()): return await _serial_start(project_id,body)

    async def _serial_start(project_id:str,body:UploadBody)->dict[str,Any]:
        graph=_record(application,project_id).graph
        await run_in_threadpool(_stop_serial,project_id)
        if _monitor_owner(body.port) not in (None,project_id): raise HTTPException(409,detail={"code":"PORT_BUSY","message":"Another project is monitoring this port."})
        if project_id in uploading or body.port in uploading_ports: raise HTTPException(409,detail={"code":"PORT_BUSY","message":"An upload is using this port."})
        fake=body.port==FAKE_PORT and fake_enabled()
        if fake:
            try: artifact,_=_effective_firmware(project_id,graph)
            except FirmwareUnsupported as exc: raise HTTPException(422,detail={"code":"FIRMWARE_UNSUPPORTED","reasons":list(exc.reasons)}) from exc
            session=SerialSession(body.port,artifact.revision_id,fake_source=lambda stop:fake_board(artifact,stop))
        else:
            cli=find_cli()
            if cli is None: raise HTTPException(422,detail={"code":"TOOLCHAIN_MISSING","missing":"arduino-cli"})
            session=SerialSession(body.port,graph.current_revision_id,cli=cli)
        try: session.start()
        except OSError as exc: raise HTTPException(422,detail={"code":"MONITOR_FAILED","message":str(exc)[:300]}) from exc
        serial_sessions[project_id]=session;busy_ports[body.port]=project_id
        return {"running":True,"port":body.port,"fake":fake}

    @app.post("/api/projects/{project_id}/serial/stop")
    async def serial_stop(project_id:str)->dict[str,Any]:
        async with serial_locks.setdefault(project_id,asyncio.Lock()): await run_in_threadpool(_stop_serial,project_id)
        return {"running":False}

    @app.get("/api/projects/{project_id}/serial")
    def serial_lines(project_id:str,after:int=0)->dict[str,Any]:
        graph=_record(application,project_id).graph;session=serial_sessions.get(project_id)
        stored=application.repository.get_hardware_evidence(project_id)
        if session is None: return {"running":False,"port":None,"fake":False,"lines":[],"wrongRevision":None,"evidence":stored}
        every=session.lines(0);current=_expected_board_revision(project_id,graph)
        latest=next((line["telemetry"] for line in reversed(every) if line["telemetry"]),None)
        wrong={"board":str(latest["rev"]),"current":current} if latest and latest["rev"]!=current else None
        found=evidence(every,current,port=session.port,fake=session.fake)
        # Evidence is only ever written from real-port telemetry for the current revision.
        if found and (stored is None or stored.get("revisionId")!=current or stored.get("port")!=session.port):
            application.repository.save_hardware_evidence(project_id,found);stored=found
        return {"running":session.running,"port":session.port,"fake":session.fake,"lines":[line for line in every if line["seq"]>after],"wrongRevision":wrong,"evidence":stored}

    def stop_all_serial()->None:
        for project_id in list(serial_sessions): _stop_serial(project_id)
    app.router.on_shutdown.append(stop_all_serial)

    @app.post("/api/projects/{project_id}/firmware/compile")
    async def compile_firmware(project_id:str)->dict[str,Any]:
        graph=_record(application,project_id).graph
        try: artifact,_=_effective_firmware(project_id,graph)
        except FirmwareUnsupported as exc: raise HTTPException(422,detail={"code":"FIRMWARE_UNSUPPORTED","reasons":list(exc.reasons)}) from exc
        # One compile per project at a time, so repeated clicks cannot exhaust the worker pool.
        if project_id in firmware_compiling: raise HTTPException(409,detail={"code":"COMPILE_IN_PROGRESS"})
        firmware_compiling.add(project_id)
        try: result=await run_in_threadpool(compile_sketch,artifact)
        finally: firmware_compiling.discard(project_id)
        if result.revision_id==_record(application,project_id).graph.current_revision_id: firmware_compiles[project_id]=result
        return result.to_dict()

    def _control_rules(ios:list[Any],requirements:dict[str,Any])->dict[str,Any]:
        provider=application.provider;reason="No live model is configured"
        if not any(io.supported for io in ios): reason="No part wired to the controller has a driver yet"
        elif provider is not None and hasattr(provider,"generate_structured"):
            try:
                payload=run_rules(provider,ios,requirements)
                return {"rules":validate_rules(payload,ios),"source":"live_model","explanation":str(payload.get("explanation","")),"reason":None}
            except RuleError as exc: reason=f"{exc.code}: {exc}"
            except Exception as exc: reason=f"Model rule list unavailable ({exc.__class__.__name__})"
        return {"rules":default_rules(ios),"source":"default","explanation":"Default rule — not generated by the live model","reason":reason}

    def _idea(session_id:str)->dict[str,Any]:
        session=application.repository.get_idea_session(session_id)
        if session is None: raise HTTPException(404,detail={"code":"IDEA_NOT_FOUND"})
        return session

    async def _idea_turn(session:dict[str,Any],text:str)->dict[str,Any]:
        try: provider=application.provider or application._default_provider()
        except RuntimeError as exc: raise HTTPException(503,detail={"code":"MODEL_UNAVAILABLE","message":str(exc),"sessionId":session["sessionId"]}) from exc
        if provider is None or not hasattr(provider,"generate_structured"):
            raise HTTPException(503,detail={"code":"MODEL_UNAVAILABLE","message":"Idea conversations need a configured model provider.","sessionId":session["sessionId"]})
        application.provider=provider
        try: updated=await run_in_threadpool(run_turn,provider,session,text)
        except Exception as exc:
            name=exc.__class__.__name__
            status,code=(503,"MODEL_AUTHENTICATION") if "Authentication" in name else (504,"MODEL_TIMEOUT") if "Timeout" in name else (502,"MODEL_UNAVAILABLE")
            raise HTTPException(status,detail={"code":code,"message":str(exc),"sessionId":session["sessionId"]}) from exc
        application.repository.save_idea_session(updated)
        return updated

    @app.post("/api/ideas",status_code=201)
    async def create_idea(body:IdeaBody)->dict[str,Any]:
        session=new_session(body.idea);session["planningMode"]=body.planningMode
        # Saved before the first model call, so a provider failure never loses the idea.
        application.repository.save_idea_session(session)
        return await _idea_turn(session,body.idea)

    @app.get("/api/ideas/{session_id}")
    def get_idea(session_id:str)->dict[str,Any]: return _idea(session_id)

    @app.post("/api/ideas/{session_id}/messages")
    async def idea_message(session_id:str,body:IdeaMessageBody)->dict[str,Any]:
        return await _idea_turn(_idea(session_id),body.text)

    @app.post("/api/ideas/{session_id}/proposal")
    async def idea_proposal(session_id:str)->dict[str,Any]:
        session=_idea(session_id)
        if session["scope"]["status"]=="OUT_OF_SCOPE":
            raise HTTPException(409,detail={"code":"OUT_OF_SCOPE","reasons":session["scope"]["reasons"],"alternative":session["scope"]["alternative"]})
        if not ready_to_propose(session):
            raise HTTPException(409,detail={"code":"REQUIREMENTS_INCOMPLETE","message":"Agree what the device does and how it is powered first."})
        objective=compose_objective(session)[:2000]
        body=CreateProjectBody(objective=objective,planningMode=session.get("planningMode","live_model"))
        try: outcome=await run_in_threadpool(application.plan,body)
        except ValueError as exc:
            raise HTTPException(422,detail=exc.args[0] if exc.args and isinstance(exc.args[0],dict) else {"status":"UNSUPPORTED","reasons":[str(exc)]}) from exc
        except RuntimeError as exc: raise HTTPException(503,detail={"code":"MODEL_UNAVAILABLE","message":str(exc)}) from exc
        verifier=VerificationService();verified=verifier.verify(outcome.plan)
        if not verified.accepted:
            repair=(lambda:LivePlanner(application.provider,application.planner_timeout).repair(outcome.plan,verified)) if outcome.mode=="live_model" and application.provider is not None else (lambda:PlannerService().repair(outcome.plan,verified))
            outcome=replace(outcome,plan=(await run_in_threadpool(repair)).plan);verified=verifier.verify(outcome.plan)
            if not verified.accepted:
                raise HTTPException(422,detail={"code":"PLAN_REJECTED","message":"AURA could not produce a design that passes its checks for these requirements.","reasons":list(verified.reasons)})
        proposal_id=f"proposal-{uuid4().hex}"
        preview=WorkspaceBridge().commit(EngineeringGraph(outcome.plan.entities[0].id),verified);ios=io_points(preview)
        try: generate_fan_sketch(preview);fan_workflow=True
        except FirmwareUnsupported: fan_workflow=False
        # The fan workflow keeps its fixed fanControl sketch, so no rule list is asked for or promised.
        control={"rules":[],"source":"fan_workflow","explanation":"Fan workflow: fixed fanControl thresholds, editable in the Code space.","reason":None} if fan_workflow             else await run_in_threadpool(_control_rules,ios,session["requirements"])
        control["bindings"]={io.id:io.component_id for io in ios}
        card=proposal_card(proposal_id,objective,session,outcome.plan,verified.findings)|{"planningMode":outcome.mode,"fallbackReason":outcome.fallback_reason,
              "controlRules":control,"ios":[asdict(io) for io in ios]}
        included=wants_breadboard(session["requirements"],session.get("families",[]),[session.get("originalIdea",""),*(m["text"] for m in session.get("messages",[]) if m.get("role")=="user")])
        card["breadboard"]={"included":included,"reason":"Prototype of plug-in modules: they sit on an 830-point breadboard (nominal standard size). You can leave it out."
                            if included else "Not added: the requirements mention a PCB or enclosure."}
        _remember_bounded(application.idea_proposals,proposal_id,(session_id,objective,outcome))
        session["proposal"]=card;session["updatedAt"]=datetime.now(timezone.utc).isoformat()
        application.repository.save_idea_session(session)
        return card

    @app.post("/api/ideas/{session_id}/approve",status_code=201)
    async def idea_approve(session_id:str,body:IdeaApproveBody)->dict[str,Any]:
        session=_idea(session_id);cached=application.idea_proposals.get(body.proposalId)
        if cached is None or cached[0]!=session_id or (session.get("proposal") or {}).get("proposalId")!=body.proposalId:
            raise HTTPException(409,detail={"code":"PROPOSAL_EXPIRED","message":"This proposal is no longer available. Propose the design again."})
        _,objective,outcome=cached;creation_info:dict[str,Any]={}
        create_body=CreateProjectBody(objective=objective,planningMode=session.get("planningMode","live_model"),operationId=body.proposalId)
        record=await application.create(create_body,creation_info=creation_info,outcome=outcome)
        if creation_info.get("reusedProject"):
            raise HTTPException(409,detail={"code":"PROJECT_EXISTS","projectId":record.project_id,"message":"A project with these requirements already exists. Open it, or change a requirement."})
        control=(session.get("proposal") or {}).get("controlRules")
        # Approval covers the rule list shown on the card; firmware reads it from here.
        if control: application.repository.save_control_rules(record.project_id,{key:control.get(key) for key in ("rules","source","explanation","bindings")})
        breadboard=body.breadboard if body.breadboard is not None else bool(((session.get("proposal") or {}).get("breadboard") or {}).get("included"))
        if breadboard:
            # Added as its own verified revision, so it shows in history and can be undone like any library add.
            board=propose_add_components(record.graph,len(record.graph.revisions),["breadboard-830"])
            _remember_bounded(application.modification_proposals,board.proposal_id,board)
            await commit_modification(record.project_id,board.proposal_id,None)
            record=_record(application,record.project_id)
        session["projectId"]=record.project_id;session["updatedAt"]=datetime.now(timezone.utc).isoformat()
        application.repository.save_idea_session(session)
        return _project_payload(record,assessment=application.assessment(record,reused_project=creation_info.get("reusedProject")))

    @app.get("/api/projects/{project_id}/work")
    def list_work(project_id:str)->dict[str,Any]:
        _record(application,project_id); items=[item.to_dict() for item in application.work_service.list(project_id)]
        return {"items":items,"summary":application.work_service.summary(project_id)}

    @app.post("/api/projects/{project_id}/work",status_code=201)
    def create_work(project_id:str,body:WorkItemBody)->dict[str,Any]:
        try:return application.work_service.create(project_id,body.title,body.description,body.category,body.relatedComponentIds,body.relatedRequirementIds,body.relatedFindingIds,_record(application,project_id).graph.current_revision_id,body.source).to_dict()
        except WorkDomainError as exc:return work_error(exc)

    @app.post("/api/projects/{project_id}/work/{work_item_id}/transition")
    def transition_work(project_id:str,work_item_id:str,body:WorkTransitionBody)->dict[str,Any]:
        try:return application.work_service.transition(project_id,work_item_id,body.targetState,body.reason,body.actor).to_dict()
        except WorkDomainError as exc:return work_error(exc)

    @app.post("/api/projects/{project_id}/work/command")
    def command_work(project_id:str,body:WorkCommandBody)->dict[str,Any]:
        command=body.command.lower(); verbs=(("pause","PAUSED"),("skip","SKIPPED"),("abandon","ABANDONED"),("resume","IN_PROGRESS"),("start","IN_PROGRESS"),("complete","COMPLETED")); target=next((state for verb,state in verbs if verb in command),None)
        if not target: raise HTTPException(422,detail={"code":"WORK_COMMAND_UNSUPPORTED","message":"State action was not recognized."})
        items=application.work_service.list(project_id); matches=[item for item in items if item.title.lower() in command or all(word in command for word in item.title.lower().split() if len(word)>3)]
        if len(matches)!=1: raise HTTPException(422,detail={"code":"WORK_ITEM_AMBIGUOUS","message":"Name one engineering work item."})
        reason=body.reason
        if not reason and " because " in command: reason=body.command[command.index(" because ")+9:]
        try:return application.work_service.transition(project_id,matches[0].id,target,reason,body.actor).to_dict()
        except WorkDomainError as exc:return work_error(exc)

    @app.post("/api/projects/{project_id}/scenarios")
    async def create_scenario(project_id:str,body:ScenarioBody)->dict[str,Any]:
        record=_record(application,project_id)
        try:
            assessment=None;model_metadata=None
            if body.changeType=="REPLACE_COMPONENT":
                provider=application.provider or application._default_provider()
                if provider is None or not hasattr(provider,"generate_structured"):
                    raise ScenarioError("SCENARIO_AI_UNAVAILABLE","What-If replacement analysis requires a configured structured AI provider",503)
                application.provider=provider
                assessment,model_metadata=await run_in_threadpool(LiveScenarioAnalyzer(provider).assess_replacement,record.graph,body.targetSemanticId,body.value)
            scenario=analyze_scenario(record.graph,body.targetSemanticId,body.changeType,body.value,assessment,model_metadata)
            candidate = replace(record, graph=scenario.candidate_graph)
            exact = VerificationService().verify_graph(scenario.candidate_graph)
            scenario.analysis["assessment"] = application._revision_assessment(candidate, exact).to_dict()
            scenario.analysis["assessmentContext"] = "CANDIDATE_NOT_COMMITTED"
        except ScenarioError as exc:raise HTTPException(exc.status,detail={"code":exc.code,"message":exc.message}) from exc
        except Exception as exc:
            error_name=exc.__class__.__name__
            status=503 if error_name=="VertexAuthenticationError" else 504 if error_name=="VertexTimeoutError" else 502
            raise HTTPException(status,detail={"code":"SCENARIO_AI_UNAVAILABLE","message":str(exc)}) from exc
        _remember_bounded(application.scenarios,scenario.id,scenario);return scenario.to_dict()

    @app.delete("/api/projects/{project_id}/scenarios/{scenario_id}")
    def discard_scenario(project_id:str,scenario_id:str)->dict[str,bool]:
        scenario=application.scenarios.get(scenario_id)
        if not scenario or scenario.project_id!=project_id:raise HTTPException(404,detail={"code":"SCENARIO_NOT_FOUND"})
        application.scenarios.pop(scenario_id,None);return {"discarded":True}

    @app.post("/api/projects/{project_id}/scenarios/{scenario_id}/apply")
    async def apply_scenario(project_id:str,scenario_id:str)->dict[str,Any]:
        scenario=application.scenarios.get(scenario_id);record=_record(application,project_id)
        if not scenario or scenario.project_id!=project_id:raise HTTPException(404,detail={"code":"SCENARIO_NOT_FOUND"})
        if not scenario.analysis.get("applicable",False):raise HTTPException(422,detail={"code":"SCENARIO_NOT_APPLICABLE","message":"AI compatibility analysis did not approve this direct replacement"})
        if scenario.base_revision!=len(record.graph.revisions) or scenario.base_revision_id!=record.graph.current_revision_id:raise HTTPException(409,detail={"code":"SCENARIO_STALE","message":"Project changed; re-run analysis."})
        lock=application.try_modification_lock(project_id)
        if lock is None:raise HTTPException(409,detail={"code":"SCENARIO_APPLY_IN_PROGRESS"})
        try:
            record=_record(application,project_id)
            if scenario.base_revision!=len(record.graph.revisions) or scenario.base_revision_id!=record.graph.current_revision_id:raise HTTPException(409,detail={"code":"SCENARIO_STALE","message":"Project changed; re-run analysis."})
            verified=VerificationService().verify_modification(record.graph,scenario.patch)
            if not verified.accepted or verified.patch is None:raise HTTPException(422,detail={"code":"SCENARIO_INVALID","reasons":list(verified.reasons)})
            updated=WorkspaceBridge().commit(record.graph,verified); now=datetime.now(timezone.utc).isoformat()
            diff=scenario.analysis["diff"];affected=scenario.analysis["impact"]["affectedComponentIds"]
            previous=[RepresentationRecord.from_dict(item) for item in record.representations]
            representations=[];lifecycle=[]
            for current in previous:
                if scenario.target_id not in current.semantic_ids and current.type is not RepresentationType.CIRCUIT_SCHEMATIC:
                    representations.append(current.to_dict());continue
                if scenario.change_type=="REMOVE_COMPONENT" and scenario.target_id in current.semantic_ids and current.type is RepresentationType.MECHANICAL_3D:
                    lifecycle.append({"type":"representation.removed","semantic_ids":list(current.semantic_ids),"payload":{"representationId":current.representation_id}});continue
                regenerated=await run_in_threadpool(application.representation_service.regenerate,updated,current)
                representations.append(regenerated.to_dict())
                lifecycle.extend([
                    {"type":"representation.stale","semantic_ids":list(current.semantic_ids),"payload":{"representationId":current.representation_id}},
                    {"type":"representation.generating","semantic_ids":list(current.semantic_ids),"payload":{"representationId":current.representation_id}},
                    {"type":f"representation.{regenerated.status.value}","semantic_ids":list(current.semantic_ids),"payload":{"representationId":current.representation_id,"artifactId":regenerated.artifact_id,"error":regenerated.error}},
                ])
            readiness_status={"BUILD_INCOMPLETE":"build_incomplete","SUPPORTED_WITH_LIMITATIONS":"ready_with_limitations","SUPPORTED":"ready"}[verification_readiness(verified)]
            updated_record=StoredProject(record.project_id,record.objective,record.planning_mode,record.fallback_reason,readiness_status,updated,representations,record.created_at,now)
            exact = VerificationService().verify_graph(updated)
            assessment = application._revision_assessment(updated_record, exact)
            result={"projectId":project_id,"previousRevisionId":scenario.base_revision_id,"newRevisionId":updated.current_revision_id,"revision":len(updated.revisions),"targetSemanticId":scenario.target_id,"changedComponentIds":diff["changedComponents"],"affectedComponentIds":affected,"changedRelationshipIds":diff["changedRelationships"],"diff":diff,"representations":representations,"verificationDelta":verified.verification_delta,"assessment":assessment.to_dict()}
            # Preview proof belongs to its ephemeral candidate, not this revision.
            analysis = {key: value for key, value in scenario.analysis.items() if key not in {"assessment", "assessmentContext"}}
            events=application.repository.save_commit(updated_record,verified.patch,{"kind":"scenario","analysis":analysis,"verificationDelta":verified.verification_delta,"workspaceAssessment":assessment.to_dict()},[{"type":"scenario.applied","semantic_ids":affected,"payload":{"scenarioId":scenario.id,"result":result}},*lifecycle])
            await application.publish_with_narration(events,updated,representations);application.scenarios.pop(scenario_id,None)
            return result
        finally:
            application.release_modification_lock(project_id,lock)

    @app.post("/api/projects/{project_id}/scenarios/{scenario_id}/work",status_code=201)
    def scenario_work(project_id:str,scenario_id:str)->dict[str,Any]:
        scenario=application.scenarios.get(scenario_id)
        if not scenario or scenario.project_id!=project_id:raise HTTPException(404,detail={"code":"SCENARIO_NOT_FOUND"})
        uncertainties=[x for x in scenario.analysis["explanations"] if x["kind"]=="UNCERTAINTY"]
        if not uncertainties:raise HTTPException(409,detail={"code":"SCENARIO_HAS_NO_UNCERTAINTY"})
        title=f"Verify {scenario.analysis['candidate']['component']['name'] if scenario.analysis['candidate']['component'] else scenario.analysis['current']['component']['name']} capability"
        findings=[x.get("findingId") for x in uncertainties if x.get("findingId")]
        return application.work_service.create(project_id,title,"Resolve uncertainty introduced by What-If analysis.","verification",[scenario.target_id],[],findings,scenario.base_revision_id,"what_if").to_dict()

    @app.websocket("/api/projects/{project_id}/events")
    async def events(websocket: WebSocket, project_id: str,
                     after_event_id: int = Query(0, alias="afterEventId", ge=0)) -> None:
        await websocket.accept()
        queue: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=application.broker.listener_queue_size)
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


def _project_payload(record: StoredProject, concise: bool = False, *, assessment: WorkspaceAssessment | None = None) -> dict[str, Any]:
    graph = record.graph
    project=graph.entities.get(graph.project_id)
    generation=project.metadata if project else {}
    if assessment is None:
        assessment = assess_workspace(operational_status=record.status, assessed_revision_id=None, revision_number=0,
            current_revision_id=graph.current_revision_id, current_revision_number=0,
            planning_origin=PlanningOrigin(planning_mode=record.planning_mode, fallback_reason=record.fallback_reason))
    return {"projectId": graph.project_id, "objective": record.objective,
            "capability": classify_objective(record.objective),
            "planningMode": record.planning_mode, "fallbackReason": record.fallback_reason,
            "revision": len(graph.revisions), "status": record.status,
            "createdAt": record.created_at, "updatedAt": record.updated_at,
            "generationMessage":generation.get("userMessage"),"userIssues":generation.get("userIssues",[]),
            "assessment":assessment.to_dict(),
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
