from __future__ import annotations

from collections.abc import Callable

from aura.engineering_graph.model import EngineeringGraph
from aura.engineering_graph.patches import apply_patch
from aura.verification.results import VerificationResult

from .events import WorkspaceEvent


class WorkspaceBridge:
    """Commit verified graph changes and publish frontend-neutral events."""

    def __init__(self) -> None:
        self._listeners: list[Callable[[WorkspaceEvent], None]] = []
        self._events: list[WorkspaceEvent] = []

    @property
    def events(self) -> tuple[WorkspaceEvent, ...]:
        return tuple(self._events)

    def subscribe(self, listener: Callable[[WorkspaceEvent], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def emit(self, event: WorkspaceEvent) -> None:
        self._events.append(event)
        for listener in tuple(self._listeners):
            listener(event)

    def commit(self, graph: EngineeringGraph, result: VerificationResult) -> EngineeringGraph:
        if not result.accepted or result.patch is None:
            self.emit(WorkspaceEvent(
                "verification.failed", graph.project_id,
                payload={"reasons": list(result.reasons), "state": result.state.value},
            ))
            return graph
        self.emit(WorkspaceEvent("verification.completed", graph.project_id, payload={"state": result.state.value}))
        updated = apply_patch(graph, result.patch)
        self.emit(WorkspaceEvent(
            "revision.committed", updated.project_id,
            revision_id=updated.current_revision_id,
            payload={"patch_id": result.patch.id},
        ))
        self.emit(WorkspaceEvent(
            "project.created", updated.project_id,
            revision_id=updated.current_revision_id, entity_id=updated.project_id,
        ))
        return updated
