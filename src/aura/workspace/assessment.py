"""Pure, revision-bound assessments; never an operational lifecycle controller.

Original-request parsing is deliberately bounded; residual intent is unassessed.
This module does not run verifiers, retrieve evidence, evaluate CAD or persist data.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from collections.abc import Mapping
from enum import Enum
import hashlib
import math
import re
from typing import Any
from pint.errors import PintError

from aura.engineering_graph.model import EngineeringGraph, EntityKind
from aura.verification.units import convert
from aura.verification.evidence import EvidenceKind, EvidenceRecord
from aura.verification.results import CheckCoverage, VerificationResult, VerificationState
from aura.workspace.representations import (
    RepresentationRecord, RepresentationSpec, RepresentationStatus, RepresentationType,
)


class AssessmentFreshness(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class RequestState(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    FULFILLED = "FULFILLED"
    PARTIAL = "PARTIAL"
    UNSUPPORTED = "UNSUPPORTED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    STALE = "STALE"


class SoftwareCheckState(str, Enum):
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"
    STALE = "STALE"


class EngineeringEvidenceState(str, Enum):
    NOT_VERIFIED = "NOT_VERIFIED"
    LIMITED = "LIMITED"
    INVALID = "INVALID"
    STALE = "STALE"


class EvidenceOrigin(str, Enum):
    DECLARED = "DECLARED"
    CURATED = "CURATED"
    RETRIEVED = "RETRIEVED"
    MEASURED = "MEASURED"
    UNKNOWN = "UNKNOWN"


class RepresentationKind(str, Enum):
    PROCEDURAL_PROXY = "PROCEDURAL_PROXY"
    CAD_UNVERIFIED = "CAD_UNVERIFIED"
    ABSTRACT_NETLIST = "ABSTRACT_NETLIST"
    NONE = "NONE"


class ArtifactState(str, Enum):
    NOT_READY = "NOT_READY"
    READY = "READY"
    FAILED = "FAILED"
    STALE = "STALE"


class CadEvaluationState(str, Enum):
    NOT_RUN = "NOT_RUN"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ObligationDisposition(str, Enum):
    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    UNASSESSED = "UNASSESSED"


REQUEST_SCOPE = (
    "Declared component family presence/minimum quantity, named identity, exact targeted "
    "voltage/length properties and explicit supply-to-component power edges; "
    "no behavioral, mechanical, evidence or physical validation"
)


@dataclass(frozen=True)
class RequestObligation:
    id: str
    original_text: str
    start: int
    end: int
    kind: str
    target_family: str | None = None
    property_name: str | None = None
    value: float | None = None
    unit: str | None = None
    quantity: int | None = None
    required: bool = True
    support_scope: str = REQUEST_SCOPE
    reason: str | None = None
    target_definition_id: str | None = None
    related_family: str | None = None
    relationship_type: str | None = None
    reference_only: bool = False


@dataclass(frozen=True)
class RequestLedger:
    original_objective: str
    objective_digest: str
    obligations: tuple[RequestObligation, ...]
    evaluation_scope: str = REQUEST_SCOPE

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RequestLedger":
        ledger = _restore_assessment_record(cls, value)
        if ledger.objective_digest != hashlib.sha256(ledger.original_objective.encode("utf-8")).hexdigest():
            raise ValueError("Original request digest does not match")
        ids = set()
        for item in ledger.obligations:
            if item.id in ids or not (0 <= item.start < item.end <= len(ledger.original_objective)) or (
                ledger.original_objective[item.start:item.end] != item.original_text
            ):
                raise ValueError("Original obligation identity or text span does not match")
            ids.add(item.id)
        return ledger


@dataclass(frozen=True)
class ObligationResult:
    obligation: RequestObligation
    disposition: ObligationDisposition
    matched_semantic_ids: tuple[str, ...] = ()
    checked_property: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class RequestAssessment:
    state: RequestState = RequestState.NOT_ASSESSED
    evaluation_scope: str | None = None
    satisfied_count: int = 0
    missing_count: int = 0
    unassessed_count: int = 0
    reasons: tuple[str, ...] = ()
    obligations: tuple[ObligationResult, ...] = ()
    original_objective_digest: str | None = None

    def __post_init__(self) -> None:
        if min(self.satisfied_count, self.missing_count, self.unassessed_count) < 0:
            raise ValueError("Obligation counts cannot be negative")
        if self.state is RequestState.FULFILLED and (
            not self.evaluation_scope or not self.evaluation_scope.strip()
            or not self.satisfied_count or self.missing_count or self.unassessed_count
        ):
            raise ValueError("Fulfillment requires an explicit scope and satisfied obligations only")


# A bounded noun vocabulary maps to graph metadata, never planner prose or names.
# More specific nouns come first so a stepper cannot be reduced to a generic motor.
_REQUEST_COMPONENTS = (
    (r"(?:NEMA\s*\d+\s+)?stepper\s+motors?", "stepper_motor", None),
    (r"(?:linear\s+guide\s+rails?|linear\s+guides?|guide\s+rails?|rails?)", "linear_guide", None),
    (r"(?:end\s+)?limit\s+switch(?:es)?", "limit_switch", None),
    (r"lead[ -]screws?", "lead_screw", None),
    (r"(?:moving\s+camera\s+)?carriages?", "carriage", None),
    (r"(?:symmetric\s+sliding\s+|sliding\s+)?jaws?", "jaw", None),
    (r"racks?", "rack", None),
    (r"pinions?", "pinion", None),
    (r"Arduino\s+Nano", "microcontroller_board", "arduino-nano-v3"),
    (r"ESP32", "microcontroller_board", "esp32-devkit-v1"),
    (r"(?:power\s+(?:supply|source)|supply)", "low_voltage_power_source", None),
    (r"mounting\s+plates?", "mounting_plate", None),
    (r"motor\s+drivers?", "motor_driver", None),
    (r"(?:NEMA\s*\d+\s+)?(?:DC\s+)?motors?", "small_dc_motor", None),
    (r"servos?", "servo", None),
    (r"microcontrollers?|controllers?", "microcontroller_board", None),
    (r"pumps?", "small_dc_pump", None),
    (r"enclosures?", "enclosure", None),
    (r"wheels?", "drive_wheel", None),
)
_NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
_QUANTITIES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
_FILLER = {"use", "include", "provide", "build", "design", "a", "an", "the", "with", "and", "to", "of", "at", "rated"}


def collect_request_obligations(objective: str) -> RequestLedger:
    """Extract declared noun/quantity/property constraints; retain every residual token.

    This is not a general language parser. Alternatives, inequalities, negation,
    behavior, ambiguous targets and unrecognized units remain UNASSESSED.
    """
    digest = hashlib.sha256(objective.encode("utf-8")).hexdigest()
    consumed = [False] * len(objective)
    obligations: list[RequestObligation] = []

    def add(start: int, end: int, kind: str, **constraints: Any) -> None:
        identity = f"{digest}:{start}:{end}:{kind}:{constraints}"
        obligations.append(RequestObligation(
            "obligation-" + hashlib.sha256(identity.encode()).hexdigest()[:16],
            objective[start:end], start, end, kind, **constraints,
        ))
        consumed[start:end] = [True] * (end - start)

    components: list[tuple[int, int, str, str | None]] = []
    for pattern, family, definition in _REQUEST_COMPONENTS:
        for match in re.finditer(r"\b" + pattern + r"\b", objective, re.I):
            if any(consumed[match.start():match.end()]):
                continue
            start = match.start()
            prefix = objective[:start]
            count = re.search(
                r"\b(one|two|three|four|five|six|seven|eight|\d+)\s+(?:" + _NUMBER + r"\s*V\s+)?$",
                prefix, re.I,
            )
            amount = 1
            if count:
                raw = count.group(1).lower()
                amount = _QUANTITIES.get(raw, int(raw) if raw.isdigit() else 1)
                start = count.start()
            # NEMA identifiers are preserved, but not interpreted as motor counts.
            clause_start = max((m.end() for m in re.finditer(r"[;.!?]", objective[:start])), default=0)
            reference = bool(re.match(r"\s*connect\b", objective[clause_start:start], re.I))
            add(start, match.end(), "component" if amount > 0 else "unassessed", target_family=family,
                target_definition_id=definition, quantity=amount, reference_only=reference,
                reason=None if amount > 0 else "Zero/absence constraints are outside the presence grammar")
            components.append((start, match.end(), family, definition))
            model = re.search(r"NEMA\s*\d+", match.group(), re.I)
            if model:
                add(match.start() + model.start(), match.start() + model.end(), "unassessed",
                    target_family=family, reason="Model/frame designation comparison is not implemented")

    # Numeric binding stays within a comma/semicolon/conjunction-delimited clause.
    # A travel/opening demand is preserved even when no comparable mechanism exists.
    for match in re.finditer(r"(?<![\w.])([+-]?" + _NUMBER + r")\s*(mm|cm|m|V|A)\b", objective, re.I):
        boundaries = list(re.finditer(r"[,;.!?]|\band\b", objective, re.I))
        left = max((b.end() for b in boundaries if b.end() <= match.start()), default=0)
        right = min((b.start() for b in boundaries if b.start() >= match.end()), default=len(objective))
        targets = [c for c in components if c[0] >= left and c[1] <= right]
        target = targets[0][2] if len(targets) == 1 else None
        definition = targets[0][3] if len(targets) == 1 else None
        raw_unit = match.group(2)
        unit = "V" if raw_unit.lower() == "v" else "A" if raw_unit.lower() == "a" else raw_unit.lower()
        property_name = "voltage_v" if unit == "V" else None
        after = re.match(r"\s*(wide|width|long|length|high|height|diameter|travel|opening)\b", objective[match.end():], re.I)
        before = re.search(r"\b(width|length|height|diameter|travel|opening)\s*(?:of\s*)?$", objective[left:match.start()], re.I)
        dimension = after.group(1).lower() if after else before.group(1).lower() if before else None
        if unit in {"mm", "cm", "m"} and dimension:
            property_name = {"wide": "width", "long": "length", "high": "height"}.get(dimension, dimension)
        end = match.end() + (after.end() if after else 0)
        start = left + before.start() if before else match.start()
        # Graph families have different voltage meanings; don't compare logic to load.
        if property_name == "voltage_v" and target == "microcontroller_board":
            property_name = "logic_voltage_v"
        if property_name == "voltage_v" and target == "motor_driver":
            property_name = "load_voltage_v"
        known = bool(target and property_name and unit != "A" and dimension not in {"travel", "opening"}
                     and not (unit == "V" and dimension))
        add(start, end, "property" if known else "unassessed", target_family=target,
            target_definition_id=definition, property_name=property_name,
            value=float(match.group(1)), unit=unit,
            reason=None if known else "Numeric target, property or mechanism cannot be compared reliably")

    # Only explicit supply -> named component power connection has bounded meaning.
    for match in re.finditer(r"\bconnect\b[^;.!?]+", objective, re.I):
        targets = sorted([c for c in components if c[0] >= match.start() and c[1] <= match.end()])
        if len(targets) == 2 and targets[0][2] == "low_voltage_power_source" and re.fullmatch(
            r"connect\s+(?:the\s+|a\s+)?", objective[match.start():targets[0][0]], re.I,
        ) and re.fullmatch(
            r"\s+to\s+(?:the\s+|a\s+)?", objective[targets[0][1]:targets[1][0]], re.I,
        ):
            add(match.start(), targets[1][1], "relationship", target_family=targets[0][2],
                related_family=targets[1][2], relationship_type="power")

    residual = "".join(" " if used else char for char, used in zip(objective, consumed))
    for clause in re.finditer(r"[^,;.!?]+", residual):
        tokens = [t for t in re.finditer(r"[^\s]+", clause.group()) if t.group().lower() not in _FILLER]
        if tokens:
            add(clause.start() + tokens[0].start(), clause.start() + tokens[-1].end(), "unassessed",
                reason="Original wording is outside the bounded comparison grammar")
    return RequestLedger(objective, digest, tuple(sorted(obligations, key=lambda o: (o.start, o.end, o.kind))))


def assess_request(ledger: RequestLedger, graph: EngineeringGraph) -> RequestAssessment:
    """Compare only component metadata and actual edges, never generated requirements."""
    results: list[ObligationResult] = []
    parts = graph.find(kind=EntityKind.COMPONENT)
    allocated: set[str] = set()

    def candidates(family: str | None, definition: str | None = None):
        return [p for p in parts if p.metadata.get("family") == family and (
            definition is None or (isinstance(p.metadata.get("parameters"), Mapping)
                and p.metadata["parameters"].get("component_definition_id") == definition)
        )]

    for obligation in ledger.obligations:
        found = candidates(obligation.target_family, obligation.target_definition_id)
        ids = tuple(p.id for p in found)
        state = ObligationDisposition.UNASSESSED
        reason = obligation.reason
        if obligation.kind == "component":
            if not obligation.reference_only:
                found = [p for p in found if p.id not in allocated]
            selected = found[:obligation.quantity]
            ids = tuple(p.id for p in selected)
            if not obligation.reference_only:
                allocated.update(ids)
            state = ObligationDisposition.SATISFIED if len(selected) == obligation.quantity else ObligationDisposition.MISSING
            reason = "Declared family/identity count compared; interfaces and function are not validated"
        elif obligation.kind == "property":
            if not found:
                state = ObligationDisposition.MISSING
                reason = "Requested target component is absent"
            else:
                values: list[float] = []
                invalid = False
                for part in found:
                    try:
                        if obligation.unit == "V":
                            value = part.metadata.get("parameters", {}).get(obligation.property_name)
                            unit = "V"  # Existing *_v graph property contract explicitly denotes volts.
                        else:
                            declared = part.metadata.get("dimensions", {}).get(obligation.property_name, {})
                            value, unit = declared.get("value"), declared.get("unit")
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not unit:
                            raise ValueError("Missing numeric property or units")
                        converted = convert(value, unit, obligation.unit)
                        if not math.isfinite(converted):
                            raise ValueError("Nonfinite property")
                        values.append(converted)
                    except (ValueError, TypeError, AttributeError, LookupError, PintError):
                        # Pint rejects unknown/incompatible units; never supply a default.
                        invalid = True
                if any(not math.isclose(value, obligation.value, rel_tol=1e-9, abs_tol=1e-9) for value in values):
                    state = ObligationDisposition.MISSING
                    reason = "Declared property contradicts the explicit requested value"
                elif invalid:
                    reason = "Target property lacks a comparable numeric value and unit"
                else:
                    state = ObligationDisposition.SATISFIED
                    reason = "Exact declared value compared on every matching target; no source validation"
        elif obligation.kind == "relationship":
            targets = {p.id for p in candidates(obligation.related_family)}
            edges = [e for e in graph.relationships.values() if e.source_id in ids and e.target_id in targets
                     and e.type == obligation.relationship_type]
            if len(found) == len(targets) == 1:
                state = ObligationDisposition.SATISFIED if edges else ObligationDisposition.MISSING
                ids = tuple(dict.fromkeys(i for e in edges for i in (e.id, e.source_id, e.target_id)))
                reason = "Directed declared power edge compared; electrical capacity is not verified"
            else:
                reason = "Connection target is absent or ambiguous"
        results.append(ObligationResult(obligation, state, ids, obligation.property_name, reason))
    mandatory = [r for r in results if r.obligation.required]
    satisfied = sum(r.disposition is ObligationDisposition.SATISFIED for r in mandatory)
    missing = sum(r.disposition is ObligationDisposition.MISSING for r in mandatory)
    unassessed = sum(r.disposition is ObligationDisposition.UNASSESSED for r in mandatory)
    if not mandatory:
        state = RequestState.NOT_ASSESSED
    elif not missing and not unassessed and satisfied:
        state = RequestState.FULFILLED
    elif satisfied:
        state = RequestState.PARTIAL
    else:
        state = RequestState.UNSUPPORTED
    return RequestAssessment(state, ledger.evaluation_scope, satisfied, missing, unassessed,
                             ("Fulfillment is limited to declared graph constraints, not engineering validity",),
                             tuple(results), ledger.objective_digest)


@dataclass(frozen=True)
class SoftwareCheckAssessment:
    state: SoftwareCheckState
    coverage: CheckCoverage | None = None
    failed_check_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class PropertyEvidence:
    entity_id: str
    property_name: str
    record: EvidenceRecord | None = None


@dataclass(frozen=True)
class PropertyEvidenceAssessment:
    entity_id: str
    property_name: str
    evidence_id: str | None
    origin: EvidenceOrigin


@dataclass(frozen=True)
class EngineeringEvidenceAssessment:
    state: EngineeringEvidenceState
    properties: tuple[PropertyEvidenceAssessment, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepresentationInput:
    record: RepresentationRecord
    spec: RepresentationSpec | None = None


@dataclass(frozen=True)
class RepresentationAssessment:
    representation_id: str
    representation_type: RepresentationType
    semantic_ids: tuple[str, ...]
    revision: int
    kind: RepresentationKind
    artifact_state: ArtifactState
    cad_evaluation_state: CadEvaluationState = CadEvaluationState.NOT_RUN


@dataclass(frozen=True)
class PlanningOrigin:
    provider: str | None = None
    model: str | None = None
    planning_mode: str | None = None
    reused_project: bool | None = None
    fallback_reason: str | None = None
    verification_status: str | None = None


@dataclass(frozen=True)
class WorkspaceAssessment:
    operational_status: str
    assessed_revision_id: str | None
    revision_number: int
    freshness: AssessmentFreshness
    request: RequestAssessment
    software_checks: SoftwareCheckAssessment
    engineering_evidence: EngineeringEvidenceAssessment
    representations: tuple[RepresentationAssessment, ...] = ()
    original_objective_digest: str | None = None
    planning_origin: PlanningOrigin = field(default_factory=PlanningOrigin)
    limitations: tuple[str, ...] = ()
    assessment_version: int = field(default=1, init=False)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WorkspaceAssessment":
        """Restore our versioned snapshot, rejecting incomplete or invalid contracts."""
        if value.get("assessmentVersion") != 1:
            raise ValueError("Unsupported assessment version")
        result = _restore_assessment_record(cls, value)
        request = result.request
        counts = tuple(sum(item.disposition is state and item.obligation.required
                           for item in request.obligations) for state in ObligationDisposition)
        if counts != (request.satisfied_count, request.missing_count, request.unassessed_count):
            raise ValueError("Stored obligation counts disagree with their results")
        if result.software_checks.state is SoftwareCheckState.PASSED and not _complete_coverage(result.software_checks.coverage):
            raise ValueError("Passed software checks require explicit coverage")
        if result.revision_number < 0:
            raise ValueError("Invalid assessed revision number")
        return result


def _restore_assessment_record(cls: type, value: Any) -> Any:
    # Explicit nested types, without evaluating annotations or executing stored data.
    nested = {
        RequestLedger: {"obligations": RequestObligation},
        WorkspaceAssessment: {"freshness": AssessmentFreshness, "request": RequestAssessment,
            "software_checks": SoftwareCheckAssessment, "engineering_evidence": EngineeringEvidenceAssessment,
            "representations": RepresentationAssessment, "planning_origin": PlanningOrigin},
        RequestAssessment: {"state": RequestState, "obligations": ObligationResult},
        ObligationResult: {"obligation": RequestObligation, "disposition": ObligationDisposition},
        SoftwareCheckAssessment: {"state": SoftwareCheckState, "coverage": CheckCoverage},
        EngineeringEvidenceAssessment: {"state": EngineeringEvidenceState, "properties": PropertyEvidenceAssessment},
        PropertyEvidenceAssessment: {"origin": EvidenceOrigin},
        RepresentationAssessment: {"representation_type": RepresentationType, "kind": RepresentationKind,
            "artifact_state": ArtifactState, "cad_evaluation_state": CadEvaluationState},
    }
    if not isinstance(value, Mapping):
        raise ValueError("Assessment records must be objects")
    kwargs = {}
    for item in fields(cls):
        if not item.init:
            continue
        key = item.name.split("_")[0] + "".join(word.title() for word in item.name.split("_")[1:])
        raw = value[key]
        annotation = str(item.type)
        optional = " | None" in annotation
        if raw is None and optional:
            kwargs[item.name] = None
            continue
        target = nested.get(cls, {}).get(item.name)
        if annotation.startswith("tuple["):
            if not isinstance(raw, (list, tuple)):
                raise ValueError(f"Invalid assessment sequence: {key}")
            if target:
                raw = tuple(_restore_assessment_record(target, element) for element in raw)
            else:
                if any(not isinstance(element, str) for element in raw):
                    raise ValueError(f"Invalid assessment strings: {key}")
                raw = tuple(raw)
        elif target:
            raw = target(raw) if issubclass(target, Enum) else _restore_assessment_record(target, raw)
        else:
            expected = {"str": str, "int": int, "bool": bool, "float": (int, float)}.get(annotation.replace(" | None", ""))
            if expected is None or not isinstance(raw, expected) or (
                expected in (int, (int, float)) and isinstance(raw, bool)
            ):
                raise ValueError(f"Invalid assessment field: {key}")
        kwargs[item.name] = raw
    return cls(**kwargs)


def refresh_assessment(
    snapshot: WorkspaceAssessment, *, operational_status: str,
    current_revision_id: str | None, current_revision_number: int,
    representations: tuple[RepresentationRecord, ...], reused_project: bool | None = None,
) -> WorkspaceAssessment:
    """Overlay current artifact availability/lifecycle without changing revision proof."""
    current = assess_workspace(
        operational_status=operational_status, assessed_revision_id=snapshot.assessed_revision_id,
        revision_number=snapshot.revision_number, current_revision_id=current_revision_id,
        current_revision_number=current_revision_number, request=snapshot.request,
        check_coverage=snapshot.software_checks.coverage,
        original_objective_digest=snapshot.original_objective_digest,
        planning_origin=replace(snapshot.planning_origin, reused_project=reused_project),
        representations=tuple(RepresentationInput(item) for item in representations),
    )
    saved = {item.representation_id: item for item in snapshot.representations}
    overlaid = []
    for item in current.representations:
        previous = saved.get(item.representation_id)
        if previous and (previous.representation_type, previous.semantic_ids, previous.revision) == (
            item.representation_type, item.semantic_ids, item.revision
        ):
            item = replace(item, kind=previous.kind, cad_evaluation_state=previous.cad_evaluation_state)
        overlaid.append(item)
    checks = snapshot.software_checks
    evidence = snapshot.engineering_evidence
    if current.freshness is AssessmentFreshness.STALE:
        checks = replace(checks, state=SoftwareCheckState.STALE,
                         reasons=tuple(dict.fromkeys((*checks.reasons, "Assessment belongs to another revision"))))
        evidence = replace(evidence, state=EngineeringEvidenceState.STALE)
    elif current.freshness is AssessmentFreshness.UNKNOWN:
        checks = replace(checks, state=SoftwareCheckState.NOT_RUN)
        evidence = replace(evidence, state=EngineeringEvidenceState.NOT_VERIFIED)
    return replace(current, software_checks=checks, engineering_evidence=evidence,
                   representations=tuple(overlaid), limitations=snapshot.limitations)


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            item.name.split("_")[0] + "".join(
                word.title() for word in item.name.split("_")[1:]
            ): _serialize(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    return value


def _complete_coverage(coverage: CheckCoverage | None) -> bool:
    return coverage is not None and (
        bool(coverage.scope.strip()) and coverage.applicability_known
        and bool(coverage.applicable_check_ids)
        and set(coverage.applicable_check_ids) <= set(coverage.executed_check_ids)
        and not set(coverage.applicable_check_ids) & set(coverage.not_applicable_check_ids)
        and not coverage.not_evaluated_check_ids
    )


def _software_checks(
    verification: VerificationResult | None,
    coverage: CheckCoverage | None,
    freshness: AssessmentFreshness,
    revision_number: int,
) -> SoftwareCheckAssessment:
    findings = verification.findings if verification else ()
    failed = tuple(dict.fromkeys(
        item.check for item in findings
        if item.blocking or item.state is VerificationState.FAILED
    ))
    if freshness is AssessmentFreshness.STALE:
        return SoftwareCheckAssessment(
            SoftwareCheckState.STALE, coverage, failed, ("Assessment belongs to another revision",),
        )
    if freshness is AssessmentFreshness.UNKNOWN:
        return SoftwareCheckAssessment(
            SoftwareCheckState.NOT_RUN, coverage, failed, ("Revision binding is unknown",),
        )
    current_failed = tuple(dict.fromkeys(
        item.check for item in findings
        if item.revision == revision_number and (
            item.blocking or item.state is VerificationState.FAILED
        )
    ))
    if current_failed:
        return SoftwareCheckAssessment(SoftwareCheckState.FAILED, coverage, current_failed)
    if any(item.revision != revision_number for item in findings):
        return SoftwareCheckAssessment(
            SoftwareCheckState.STALE, coverage, failed, ("Check findings belong to another revision",),
        )
    if verification and verification.state is VerificationState.FAILED:
        return SoftwareCheckAssessment(SoftwareCheckState.FAILED, coverage, failed)
    if verification and (
        verification.state is VerificationState.STALE
        or any(item.state is VerificationState.STALE for item in findings)
    ):
        return SoftwareCheckAssessment(SoftwareCheckState.STALE, coverage)
    complete = _complete_coverage(coverage)
    successful = {VerificationState.CROSS_CHECKED, VerificationState.TOOL_VERIFIED}
    unresolved = coverage is not None and any(
        item.check in coverage.applicable_check_ids and item.state not in successful
        for item in findings
    )
    if complete and not unresolved and verification and verification.state in successful:
        return SoftwareCheckAssessment(SoftwareCheckState.PASSED, coverage)
    return SoftwareCheckAssessment(
        SoftwareCheckState.NOT_RUN, coverage, failed,
        ("Explicit successful check results and complete scoped coverage are required",),
    )


def _property_evidence(item: PropertyEvidence) -> PropertyEvidenceAssessment:
    record = item.record
    origin = EvidenceOrigin.UNKNOWN
    if record and item.property_name in record.properties and (
        not record.applies_to or item.entity_id in record.applies_to
    ):
        origin = (
            EvidenceOrigin.DECLARED if record.kind is EvidenceKind.ENGINEERING_ASSUMPTION
            else EvidenceOrigin.CURATED
        )
    # Legacy source_verified/retrieved_at/content_hash are not retrieval proof.
    return PropertyEvidenceAssessment(
        item.entity_id, item.property_name, record.evidence_id if record else None, origin,
    )


def _representation(
    item: RepresentationInput,
    current_revision_number: int,
    freshness: AssessmentFreshness,
) -> RepresentationAssessment:
    record, spec = item.record, item.spec
    kind = RepresentationKind.NONE
    if spec and spec.kind is record.type:
        if record.type is RepresentationType.MECHANICAL_3D:
            semantic = spec.payload.get("semanticCoverage", {})
            kind = (
                RepresentationKind.PROCEDURAL_PROXY
                if semantic.get("proxy") is True or semantic.get("renderStrategy") == "family_proxy"
                else RepresentationKind.CAD_UNVERIFIED
            )
        elif record.type is RepresentationType.CIRCUIT_SCHEMATIC:
            kind = RepresentationKind.ABSTRACT_NETLIST
    artifact = ArtifactState.NOT_READY
    if record.status is RepresentationStatus.READY and record.artifact_id:
        artifact = ArtifactState.READY
    elif record.status is RepresentationStatus.FAILED:
        artifact = ArtifactState.FAILED
    if record.status is RepresentationStatus.STALE or (
        freshness is AssessmentFreshness.STALE or record.revision != current_revision_number
    ):
        artifact = ArtifactState.STALE
    return RepresentationAssessment(
        record.representation_id, record.type, record.semantic_ids, record.revision, kind, artifact,
    )


def assess_workspace(
    *,
    operational_status: str,
    assessed_revision_id: str | None,
    revision_number: int,
    current_revision_id: str | None,
    current_revision_number: int,
    request: RequestAssessment | None = None,
    verification: VerificationResult | None = None,
    check_coverage: CheckCoverage | None = None,
    property_evidence: tuple[PropertyEvidence, ...] = (),
    representations: tuple[RepresentationInput, ...] = (),
    original_objective_digest: str | None = None,
    planning_origin: PlanningOrigin | None = None,
) -> WorkspaceAssessment:
    """Project explicit inputs conservatively without running or changing anything."""
    if revision_number != current_revision_number:
        freshness = AssessmentFreshness.STALE
    elif not assessed_revision_id or not current_revision_id:
        freshness = AssessmentFreshness.UNKNOWN
    elif assessed_revision_id != current_revision_id:
        freshness = AssessmentFreshness.STALE
    else:
        freshness = AssessmentFreshness.CURRENT
    request = request if request is not None else RequestAssessment()
    if freshness is AssessmentFreshness.STALE:
        request = replace(request, state=RequestState.STALE)
    elif freshness is AssessmentFreshness.UNKNOWN:
        request = replace(request, state=RequestState.NOT_ASSESSED)
    properties = tuple(_property_evidence(item) for item in property_evidence)
    evidence_state = EngineeringEvidenceState.NOT_VERIFIED
    if freshness is AssessmentFreshness.STALE:
        evidence_state = EngineeringEvidenceState.STALE
    elif freshness is AssessmentFreshness.CURRENT and any(
        item.origin is EvidenceOrigin.CURATED for item in properties
    ):
        evidence_state = EngineeringEvidenceState.LIMITED
    evidence = EngineeringEvidenceAssessment(
        evidence_state, properties,
        ("Property references are declared or curated; retrieval and physical validation are not established",),
    )
    return WorkspaceAssessment(
        operational_status=operational_status,
        assessed_revision_id=assessed_revision_id,
        revision_number=revision_number,
        freshness=freshness,
        request=request,
        software_checks=_software_checks(verification, check_coverage, freshness, revision_number),
        engineering_evidence=evidence,
        representations=tuple(
            _representation(item, current_revision_number, freshness) for item in representations
        ),
        original_objective_digest=original_objective_digest,
        planning_origin=planning_origin if planning_origin is not None else PlanningOrigin(),
        limitations=("No physical verification or validated CAD is established by this assessment",),
    )
