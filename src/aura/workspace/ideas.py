from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aura.capabilities import CAPABILITY_MANIFEST, classify_objective
from aura.verification.catalogue import CATALOGUE

SLOTS = ("function", "budget", "power", "connectivity", "dimensions", "environment", "experience")
REQUIRED = ("function", "power")
SOURCES = {"user", "default", "assumption"}
STATUSES = {"agreed", "proposed", "open"}
MAX_QUESTIONS = 3
_BY_ID = {item.component_definition_id: item for item in CATALOGUE}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_session(idea: str) -> dict[str, Any]:
    now = _now()
    return {"sessionId": f"idea-{uuid4().hex}", "originalIdea": idea, "messages": [],
            "requirements": {name: {"value": "", "source": "assumption", "status": "open", "tradeoff": ""} for name in SLOTS},
            "openQuestions": [], "families": [], "unsupportedNeeds": [],
            "scope": {"status": "UNKNOWN", "reasons": [], "alternative": None},
            "proposal": None, "projectId": None, "createdAt": now, "updatedAt": now}


def apply_turn(session: dict[str, Any], user_text: str, turn: dict[str, Any]) -> dict[str, Any]:
    """Merge one model turn; the model's output is a proposal that these rules filter."""
    updated = copy.deepcopy(session); now = _now()
    for item in turn.get("slots") or []:
        name = item.get("slot")
        if name not in SLOTS or not str(item.get("value") or "").strip(): continue
        updated["requirements"][name] = {"value": str(item["value"]).strip(),
            "source": item.get("source") if item.get("source") in SOURCES else "assumption",
            "status": item.get("status") if item.get("status") in STATUSES else "proposed",
            "tradeoff": str(item.get("tradeoff") or "")}
    updated["openQuestions"] = [{"slot": q["slot"], "question": str(q.get("question") or ""), "suggestedDefault": str(q.get("suggestedDefault") or ""),
                                 "tradeoff": str(q.get("tradeoff") or "")}
                                for q in (turn.get("questions") or []) if q.get("slot") in SLOTS][:MAX_QUESTIONS]
    supported = set(CAPABILITY_MANIFEST["supportedComponentFamilies"])
    for family in turn.get("families") or []:
        target = updated["families"] if family in supported else updated["unsupportedNeeds"]
        if family not in target: target.append(family)
    updated["scope"] = _scope(updated, turn.get("scope") or {})
    updated["messages"] += [{"role": "user", "text": user_text, "timestamp": now},
                            {"role": "assistant", "text": str(turn.get("reply") or ""), "timestamp": now}]
    updated["updatedAt"] = now
    return updated


def _scope(session: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    # Deterministic gate: the classifier's UNSUPPORTED always wins; the model may only narrow scope.
    verdict = classify_objective(compose_objective(session))
    alternative = model.get("alternative")
    if verdict["status"] == "UNSUPPORTED":
        return {"status": "OUT_OF_SCOPE", "reasons": list(verdict["reasons"]), "alternative": alternative or verdict.get("supportedAlternative")}
    if model.get("status") == "OUT_OF_SCOPE":
        return {"status": "OUT_OF_SCOPE", "reasons": [str(r) for r in model.get("reasons") or []], "alternative": alternative}
    if verdict["status"] in {"SUPPORTED", "SUPPORTED_WITH_LIMITATIONS"} or (model.get("status") == "IN_SCOPE" and session["families"]):
        return {"status": "IN_SCOPE", "reasons": list(verdict.get("reasons") or []), "alternative": None}
    return {"status": "UNKNOWN", "reasons": list(verdict.get("reasons") or []), "alternative": None}


def compose_objective(session: dict[str, Any]) -> str:
    req = session["requirements"]
    parts = [f"Build a low-voltage device that will {req['function']['value']}" if req["function"]["value"] else "Build a low-voltage device"]
    parts += [f"{name.capitalize()}: {req[name]['value']}" for name in SLOTS[1:] if req[name]["value"]]
    if session["families"]: parts.append("Uses: " + ", ".join(family.replace("_", " ") for family in session["families"]))
    return ". ".join(parts) + "."


def ready_to_propose(session: dict[str, Any]) -> bool:
    req = session["requirements"]
    return (req["function"]["status"] == "agreed" and bool(req["power"]["value"]) and req["power"]["status"] != "open"
            and session["scope"]["status"] == "IN_SCOPE")


def _range(item) -> tuple[float, float] | None:
    fact = item.properties.get("supply_voltage_range")
    return tuple(fact.value) if fact else None


def _value(item, name: str):
    fact = item.properties.get(name)
    return fact.value if fact else None


def rank_alternatives(definition_id: str, priority: str) -> list[dict[str, Any]]:
    """Same-family catalogue parts with overlapping supply range, ordered on documented fields only."""
    current = _BY_ID[definition_id]; low, high = _range(current) or (float("-inf"), float("inf"))
    options = [item for item in CATALOGUE if item.family == current.family
               and (_range(item) is None or (_range(item)[0] <= high and _range(item)[1] >= low))]
    def volume(item):
        size = _value(item, "dimensions")
        return size[0] * size[1] * size[2] if size else None
    metric = {"cost": lambda item: item.price["usd"] if item.price else None,
              "power": lambda item: _value(item, "current"), "size": volume}.get(priority, lambda item: item.price["usd"] if item.price else None)
    ordered = sorted(options, key=lambda item: (metric(item) is None, metric(item) or 0, item.component_definition_id))
    return [{"componentDefinitionId": item.component_definition_id, "family": item.family, "partNumber": item.part_number,
             "manufacturer": item.manufacturer, "priceUsd": item.price["usd"] if item.price else None,
             "currentMa": _value(item, "current"), "dimensionsMm": _value(item, "dimensions"),
             "evidenceIds": list(item.evidence_ids), "selected": item.component_definition_id == definition_id} for item in ordered]


def cost_summary(definition_ids: list[str]) -> dict[str, Any]:
    items, excluded = [], []
    for part in definition_ids:
        item = _BY_ID.get(part)
        if item is None or item.price is None:
            if part not in excluded: excluded.append(part)
            continue
        items.append({"componentDefinitionId": part, "usd": item.price["usd"], "source": item.price["source"], "retrieved": item.price["retrieved"]})
    return {"totalUsd": round(sum(item["usd"] for item in items), 2), "estimate": True, "excluded": excluded, "items": items}
