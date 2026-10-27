from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from aura.capabilities import CAPABILITY_MANIFEST, classify_objective, compact_capability_context
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


_TEXT = {"type": "string", "maxLength": 400}
TURN_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["slots", "questions", "families", "scope", "reply"], "properties": {
    "slots": {"type": "array", "maxItems": 7, "items": {"type": "object", "additionalProperties": False, "required": ["slot", "value", "source", "status", "tradeoff"], "properties": {
        "slot": {"type": "string", "enum": list(SLOTS)}, "value": _TEXT, "source": {"type": "string", "enum": sorted(SOURCES)},
        "status": {"type": "string", "enum": sorted(STATUSES)}, "tradeoff": _TEXT}}},
    "questions": {"type": "array", "maxItems": MAX_QUESTIONS, "items": {"type": "object", "additionalProperties": False, "required": ["slot", "question", "suggestedDefault", "tradeoff"], "properties": {
        "slot": {"type": "string", "enum": list(SLOTS)}, "question": _TEXT, "suggestedDefault": _TEXT, "tradeoff": _TEXT}}},
    "families": {"type": "array", "maxItems": 12, "items": {"type": "string", "maxLength": 60}},
    "scope": {"type": "object", "additionalProperties": False, "required": ["status", "reasons", "alternative"], "properties": {
        "status": {"type": "string", "enum": ["IN_SCOPE", "OUT_OF_SCOPE", "UNKNOWN"]}, "reasons": {"type": "array", "maxItems": 4, "items": _TEXT},
        "alternative": {"type": ["string", "null"], "maxLength": 400}}},
    "reply": {"type": "string", "maxLength": 1200}}}

_SYSTEM = """You are AURA's requirements engineer for small low-voltage IoT and mechatronic devices.
Converse with the user to agree requirements before any design is made. Rules:
- Requirement slots: {slots}. Update a slot only from what the user said (source user) or a default the user accepted (source default); mark unconfirmed guesses source assumption, status proposed.
- Ask at most 3 questions per turn, only about open slots that matter for this idea. Each question carries a reasonable suggested default and its tradeoff.
- Name the component families the design needs, using only these names: {families}.
- If the idea needs something outside the capability below, set scope OUT_OF_SCOPE, explain why in plain words, and offer an achievable low-voltage alternative.
- Never invent component ratings or prices. Never claim a part is universally best.
- reply: a short, friendly message to the user summarising what you understood and asking the questions.
Capability: {capability}
Current requirements (JSON): {requirements}
Original idea: {idea}"""


def run_turn(provider: Any, session: dict[str, Any], user_text: str) -> dict[str, Any]:
    """One structured model turn; provider errors propagate and the session is not modified."""
    history = [{"role": m["role"], "content": m["text"]} for m in session["messages"]] + [{"role": "user", "content": user_text}]
    prompt = _SYSTEM.format(slots=", ".join(SLOTS), families=", ".join(CAPABILITY_MANIFEST["supportedComponentFamilies"]),
                            capability=compact_capability_context(), requirements=json.dumps(session["requirements"]), idea=session["originalIdea"])
    result = provider.generate_structured(history, system_prompt=prompt, max_tokens=1200, response_schema=TURN_SCHEMA)
    return apply_turn(session, user_text, json.loads(result.text))
