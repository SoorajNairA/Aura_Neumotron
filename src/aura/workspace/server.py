from __future__ import annotations

import argparse
import asyncio
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from aura.engineering_graph.model import EngineeringGraph, EntityKind
from aura.engineering_graph.serialization import graph_to_dict
from aura.planner.live import LivePlanner, PlanningOutcome
from aura.planner.schemas import ProjectRequest
from aura.planner.service import PlannerService
from aura.verification.service import VerificationService
from .bridge import WorkspaceBridge
from .events import WorkspaceEvent
from .representations import RepresentationRequest, RepresentationStatus, RepresentationType


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


@dataclass
class ProjectRecord:
    graph: EngineeringGraph
    objective: str
    planning_mode: str
    fallback_reason: str | None
    representations: list[RepresentationRequest]


class EventBroker:
    def __init__(self) -> None:
        self.events: dict[str, list[EventEnvelope]] = {}
        self.listeners: dict[str, set[asyncio.Queue[EventEnvelope]]] = {}

    def reset(self, project_id: str) -> None:
        self.events[project_id] = []

    async def publish(self, project_id: str, event_type: str, semantic_ids: list[str] | None = None,
                      payload: dict[str, Any] | None = None, revision: int = 0) -> EventEnvelope:
        history = self.events.setdefault(project_id, [])
        envelope = EventEnvelope(eventId=len(history) + 1, projectId=project_id,
            revision=revision, type=event_type, semanticIds=semantic_ids or [],
            payload=payload or {}, timestamp=datetime.now(timezone.utc).isoformat())
        history.append(envelope)
        for queue in tuple(self.listeners.get(project_id, set())):
            await queue.put(envelope)
        return envelope

    def replay(self, project_id: str, after: int) -> list[EventEnvelope]:
        return [event for event in self.events.get(project_id, []) if event.eventId > after]


class WorkspaceApplication:
    def __init__(self, provider: Any | None = None, planner_timeout: float = 15.0) -> None:
        self.provider = provider
        self.planner_timeout = planner_timeout
        self.projects: dict[str, ProjectRecord] = {}
        self.broker = EventBroker()

    def _request(self, objective: str) -> ProjectRequest:
        return ProjectRequest("Automatic Irrigation System", objective,
            ("Water automatically when soil is dry", "Use low-voltage DC power", "Keep water separated from electronics"),
            assumptions=("Use a capacitive moisture sensor", "Use a splash-resistant electronics enclosure"))

    def plan(self, body: CreateProjectBody) -> PlanningOutcome:
        request = self._request(body.objective)
        if body.planningMode == "live_model":
            provider = self.provider or self._default_provider()
            if provider is not None:
                return LivePlanner(provider, self.planner_timeout).plan(request)
        mode = "deterministic_test" if body.planningMode == "deterministic_test" else "deterministic_fallback"
        reason = None if mode == "deterministic_test" else "live model was not configured"
        return PlanningOutcome(PlannerService().plan(request), mode, reason)

    @staticmethod
    def _default_provider() -> Any | None:
        try:
            from aura.config import Settings
            from aura.conversation_model import OllamaConversationModel
            from aura.infrastructure.model_provider import ConversationModelAdapter
            settings = Settings()
            model = settings.ollama_conversation_model
            if model == "auto":
                model = settings.ollama_primary_model
            return ConversationModelAdapter(OllamaConversationModel(
                model, settings.ollama_base_url, settings.ollama_request_timeout,
                settings.ollama_context_length))
        except Exception:
            return None

    async def create(self, body: CreateProjectBody) -> ProjectRecord:
        outcome = await run_in_threadpool(self.plan, body)
        plan = outcome.plan
        project_id = plan.entities[0].id
        self.broker.reset(project_id)
        await self.broker.publish(project_id, "project.started", payload={"planningMode": outcome.mode})
        if outcome.mode == "live_model":
            await self.broker.publish(project_id, "planning.live_model", payload={"message": "Planning with live model"})
        elif outcome.mode == "deterministic_fallback":
            await self.broker.publish(project_id, "task.fallback_used", payload={"reason": outcome.fallback_reason})
        verified = VerificationService().verify(plan)
        if not verified.accepted:
            await self.broker.publish(project_id, "project.failed", payload={"reasons": list(verified.reasons)})
            raise HTTPException(422, detail=list(verified.reasons))
        bridge = WorkspaceBridge()
        graph = bridge.commit(EngineeringGraph(project_id), verified)
        record = ProjectRecord(graph, body.objective, outcome.mode, outcome.fallback_reason,
            [RepresentationRequest(component.id, RepresentationType.PLACEHOLDER,
                RepresentationStatus.CONCEPTUAL) for component in graph.find(kind=EntityKind.COMPONENT)])
        self.projects[project_id] = record
        for event in bridge.events:
            if event.type == "project.started":
                continue
            await self._publish_workspace(event, graph)
        return record

    async def _publish_workspace(self, event: WorkspaceEvent, graph: EngineeringGraph) -> None:
        semantic_ids = []
        if event.entity_id:
            semantic_ids.append(event.entity_id)
        semantic_ids.extend(value for value in event.payload.get("entity_ids", []) if value not in semantic_ids)
        await self.broker.publish(event.project_id, event.type, semantic_ids, event.payload,
            len(graph.revisions) if event.revision_id else 0)

    async def modify(self, project_id: str, body: ModificationBody) -> dict[str, Any]:
        record = self.projects.get(project_id)
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
        record.graph = updated
        for event in bridge.events:
            await self._publish_workspace(event, updated)
        after_entity = updated.get(selected.id)
        after = {"id": after_entity.id, "name": after_entity.name, "revision": len(updated.revisions)}
        return {"projectId": project_id, "before": before, "after": after,
                "summary": patch.summary, "rerunChecks": [finding.check for finding in result.findings]}


def create_app(provider: Any | None = None, planner_timeout: float = 15.0) -> FastAPI:
    application = WorkspaceApplication(provider, planner_timeout)
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

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        record = _record(application, project_id)
        return _project_payload(record)

    @app.get("/api/projects/{project_id}/graph")
    def get_graph(project_id: str) -> dict[str, Any]:
        return graph_to_dict(_record(application, project_id).graph)

    @app.get("/api/projects/{project_id}/revisions")
    def get_revisions(project_id: str) -> list[dict[str, Any]]:
        return [revision.__dict__ for revision in _record(application, project_id).graph.revisions]

    @app.post("/api/projects/{project_id}/modifications")
    async def modify_project(project_id: str, body: ModificationBody) -> dict[str, Any]:
        return await application.modify(project_id, body)

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


def _record(application: WorkspaceApplication, project_id: str) -> ProjectRecord:
    try:
        return application.projects[project_id]
    except KeyError as exc:
        raise HTTPException(404, "Project not found") from exc


def _project_payload(record: ProjectRecord) -> dict[str, Any]:
    graph = record.graph
    return {"projectId": graph.project_id, "objective": record.objective,
            "planningMode": record.planning_mode, "fallbackReason": record.fallback_reason,
            "revision": len(graph.revisions), "status": "ready",
            "representations": [item.to_dict() for item in record.representations]}


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AURA browser workspace")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--open", action="store_true", dest="open_browser")
    args = parser.parse_args()
    if args.open_browser:
        webbrowser.open(f"http://{args.host}:{args.port}")
    import uvicorn
    uvicorn.run("aura.workspace.server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
