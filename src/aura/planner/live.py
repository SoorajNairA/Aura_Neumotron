from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from threading import Event
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aura.infrastructure.llm.provider import ModelProvider
from aura.capabilities import compact_capability_context
from .schemas import ProjectPlan, ProjectRequest
from .service import PlannerService


class StructuredPlannerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    projectName: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    requirements: list[str] = Field(min_length=1)
    assumptions: list[str]
    components: list[str] = Field(min_length=3)


@dataclass(frozen=True)
class PlanningOutcome:
    plan: ProjectPlan
    mode: str
    fallback_reason: str | None = None


class LivePlanner:
    """Bounded structured-model adapter with one repair and honest fallback."""

    def __init__(self, provider: ModelProvider, timeout_seconds: float = 15.0) -> None:
        self.provider = provider
        self.timeout_seconds = timeout_seconds

    def plan(self, request: ProjectRequest, cancel: Event | None = None) -> PlanningOutcome:
        cancel = cancel or Event()
        errors = ""
        for attempt in range(2):
            if cancel.is_set():
                return self._fallback(request, "planning cancelled")
            prompt = self._prompt(request, errors)
            try:
                raw = self._generate(prompt)
                structured = StructuredPlannerResponse.model_validate(json.loads(raw))
                planned_request = ProjectRequest(
                    structured.projectName, structured.objective,
                    tuple(structured.requirements), assumptions=tuple(structured.assumptions),
                )
                plan = PlannerService().plan(planned_request)
                plan.validate()
                return PlanningOutcome(plan, "live_model")
            except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                errors = str(exc)
            except FutureTimeout:
                return self._fallback(request, f"live model timed out after {self.timeout_seconds:g}s")
            except Exception as exc:
                return self._fallback(request, f"live model unavailable: {exc}")
        return self._fallback(request, f"structured response invalid after repair: {errors}")

    def _generate(self, prompt: str) -> str:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aura-planner")
        future = executor.submit(self.provider.generate,
            [{"role": "user", "content": prompt}],
            system_prompt="Return exactly one JSON object and no prose.", max_tokens=1200)
        try:
            return future.result(timeout=self.timeout_seconds)
        except FutureTimeout:
            future.cancel()
            raise
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _prompt(request: ProjectRequest, errors: str) -> str:
        repair = f" Previous validation errors: {errors}. Correct every error." if errors else ""
        return ("Plan only a bounded project within this capability manifest. " + compact_capability_context() +
                " Return JSON with exactly projectName, objective, requirements, assumptions, components. "
                "Use semantic component roles, record necessary assumptions, and do not claim unsupported verification. "
                f"Objective: {request.objective}.{repair}")

    @staticmethod
    def _fallback(request: ProjectRequest, reason: str) -> PlanningOutcome:
        return PlanningOutcome(PlannerService().plan(request), "deterministic_fallback", reason)
