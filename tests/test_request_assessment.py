from __future__ import annotations

import copy
import importlib
import importlib.util
import json

import pytest

from aura.verification.evidence import EvidenceKind, EvidenceRecord
from aura.verification.results import (
    VerificationDecision, VerificationFinding, VerificationResult, VerificationState,
)
from aura.workspace.representations import (
    RepresentationRecord, RepresentationSpec, RepresentationStatus, RepresentationType,
)


def contract():
    # Collect real behavioral tests even before this new module exists.
    assert importlib.util.find_spec("aura.workspace.assessment") is not None, (
        "Task 1.1 pure assessment contract has not been implemented"
    )
    return importlib.import_module("aura.workspace.assessment")


def project(**changes):
    return contract().assess_workspace(
        **({
            "operational_status": "ready_with_limitations",
            "assessed_revision_id": "revision-1",
            "revision_number": 1,
            "current_revision_id": "revision-1",
            "current_revision_number": 1,
        } | changes)
    )


def result(*findings, state=VerificationState.CROSS_CHECKED):
    return VerificationResult(VerificationDecision.ACCEPT, state, (), None, tuple(findings))


def proxy():
    record = RepresentationRecord(
        "repr-pump", "project-1", 1, ("component-pump",),
        RepresentationType.MECHANICAL_3D, RepresentationStatus.READY,
        generator="cascade-core", artifact_id="spec-pump",
        verification_status="tool_verified",
    )
    spec = RepresentationSpec(
        RepresentationType.MECHANICAL_3D, ("component-pump",),
        {"semanticCoverage": {"proxy": True, "renderStrategy": "family_proxy"}},
    )
    return contract().RepresentationInput(record, spec)


def covered():
    return contract().CheckCoverage(
        scope="declared_voltage",
        applicability_known=True,
        executed_check_ids=("VOLTAGE",),
        applicable_check_ids=("VOLTAGE",),
    )


def test_assessment_contract_never_infers_pass_from_empty_findings():
    c = contract()
    assessment = project(verification=result())
    assert assessment.software_checks.state is c.SoftwareCheckState.NOT_RUN
    assert assessment.engineering_evidence.state is c.EngineeringEvidenceState.NOT_VERIFIED
    assert assessment.request.state is c.RequestState.NOT_ASSESSED


@pytest.mark.parametrize("state,blocking", [
    (VerificationState.FAILED, False),
    (VerificationState.ESTIMATED, True),
])
def test_assessment_contract_failure_is_independent_of_ready(state, blocking):
    c = contract()
    finding = VerificationFinding(
        "finding-voltage", "VOLTAGE", state, "critical",
        "Declared voltage is incompatible", ("component-pump",), blocking=blocking,
    )
    assessment = project(verification=result(finding), check_coverage=covered())
    assert assessment.software_checks.state is c.SoftwareCheckState.FAILED
    assert assessment.software_checks.failed_check_ids == ("VOLTAGE",)
    assert assessment.operational_status == "ready_with_limitations"


def test_assessment_contract_overall_failed_result_without_findings_is_failed():
    c = contract()
    assessment = project(verification=result(state=VerificationState.FAILED))
    assert assessment.software_checks.state is c.SoftwareCheckState.FAILED
    assert assessment.operational_status == "ready_with_limitations"


@pytest.mark.parametrize("request_state", ["PARTIAL", "UNSUPPORTED", "NEEDS_CLARIFICATION"])
def test_assessment_contract_unfulfilled_request_preserves_operational_status(request_state):
    c = contract()
    request = c.RequestAssessment(
        state=c.RequestState(request_state), evaluation_scope="declared_mechanism",
        unassessed_count=1, reasons=("Mechanism not assessed",),
    )
    assessment = project(request=request)
    assert assessment.request.state.value == request_state
    assert assessment.operational_status == "ready_with_limitations"


def test_assessment_contract_proxy_is_not_cad_validation():
    c = contract()
    assessment = project(representations=(proxy(),))
    item = assessment.representations[0]
    assert item.kind is c.RepresentationKind.PROCEDURAL_PROXY
    assert item.artifact_state is c.ArtifactState.READY
    assert item.cad_evaluation_state is c.CadEvaluationState.NOT_RUN
    assert assessment.engineering_evidence.state is c.EngineeringEvidenceState.NOT_VERIFIED


def test_assessment_contract_nonproxy_spec_does_not_imply_cad_evaluation():
    c = contract()
    item = proxy()
    spec = RepresentationSpec(item.spec.kind, item.spec.semantic_ids, {"geometry": {"operation": "box"}})
    assessment = project(representations=(c.RepresentationInput(item.record, spec),))
    assert assessment.representations[0].kind is c.RepresentationKind.CAD_UNVERIFIED
    assert assessment.representations[0].cad_evaluation_state is c.CadEvaluationState.NOT_RUN


def test_assessment_contract_revision_mismatch_is_stale():
    c = contract()
    request = c.RequestAssessment(
        state=c.RequestState.FULFILLED, evaluation_scope="declared_voltage",
        satisfied_count=1,
    )
    assessment = project(
        current_revision_id="revision-2", current_revision_number=2,
        request=request, verification=result(), check_coverage=covered(),
        representations=(proxy(),),
    )
    assert assessment.freshness is c.AssessmentFreshness.STALE
    assert assessment.software_checks.state is c.SoftwareCheckState.STALE
    assert assessment.request.state is c.RequestState.STALE
    assert assessment.engineering_evidence.state is c.EngineeringEvidenceState.STALE
    assert assessment.representations[0].artifact_state is c.ArtifactState.STALE
    assert assessment.assessed_revision_id == "revision-1"
    assert assessment.operational_status == "ready_with_limitations"


def test_assessment_contract_same_revision_number_different_id_is_stale():
    c = contract()
    assessment = project(current_revision_id="other-branch-revision")
    assert assessment.freshness is c.AssessmentFreshness.STALE


def test_assessment_contract_missing_revision_binding_cannot_pass():
    c = contract()
    assessment = project(assessed_revision_id=None, verification=result(), check_coverage=covered())
    assert assessment.freshness is c.AssessmentFreshness.UNKNOWN
    assert assessment.software_checks.state is c.SoftwareCheckState.NOT_RUN


@pytest.mark.parametrize("kind,want", [
    (EvidenceKind.ENGINEERING_ASSUMPTION, "DECLARED"),
    (EvidenceKind.MANUFACTURER_DATASHEET, "CURATED"),
])
def test_assessment_contract_assumption_cannot_be_source_evidence(kind, want):
    c = contract()
    source = EvidenceRecord.curated(
        "evidence-voltage", kind, "Voltage reference", "https://example.test/reference",
        "Declared source", ("voltage_v",), "v1",
    ).for_targets("component-pump")
    finding = VerificationFinding(
        "finding-source", "PROPERTY_SOURCE", VerificationState.SOURCE_VERIFIED,
        "info", "Legacy sourced label", ("component-pump",),
        evidence_ids=("evidence-voltage",),
    )
    assessment = project(
        verification=result(finding, state=VerificationState.SOURCE_VERIFIED),
        property_evidence=(c.PropertyEvidence("component-pump", "voltage_v", source),),
    )
    item = assessment.engineering_evidence.properties[0]
    assert item.origin.value == want
    assert item.origin not in {c.EvidenceOrigin.RETRIEVED, c.EvidenceOrigin.MEASURED}
    if kind is EvidenceKind.ENGINEERING_ASSUMPTION:
        assert assessment.engineering_evidence.state is c.EngineeringEvidenceState.NOT_VERIFIED


def test_assessment_contract_legacy_source_label_without_evidence_remains_unknown():
    c = contract()
    finding = VerificationFinding(
        "source", "PROPERTY_SOURCE", VerificationState.SOURCE_VERIFIED, "info",
        "Legacy source_verified", ("component-pump",),
    )
    assessment = project(
        verification=result(finding, state=VerificationState.SOURCE_VERIFIED),
        property_evidence=(c.PropertyEvidence("component-pump", "voltage_v"),),
    )
    assert assessment.engineering_evidence.properties[0].origin is c.EvidenceOrigin.UNKNOWN
    assert assessment.engineering_evidence.state is c.EngineeringEvidenceState.NOT_VERIFIED


def test_assessment_contract_explicit_complete_coverage_can_pass_only_software_scope():
    c = contract()
    assessment = project(verification=result(), check_coverage=covered())
    assert assessment.software_checks.state is c.SoftwareCheckState.PASSED
    assert assessment.software_checks.coverage.scope == "declared_voltage"
    assert assessment.request.state is c.RequestState.NOT_ASSESSED
    assert assessment.engineering_evidence.state is c.EngineeringEvidenceState.NOT_VERIFIED


@pytest.mark.parametrize("changes", [
    {"applicability_known": False},
    {"executed_check_ids": ()},
    {"applicable_check_ids": ("VOLTAGE", "CURRENT")},
    {"not_evaluated_check_ids": ("CURRENT",)},
])
def test_assessment_contract_incomplete_coverage_cannot_pass(changes):
    c = contract()
    coverage = c.CheckCoverage(**({
        "scope": "declared_electrical", "applicability_known": True,
        "executed_check_ids": ("VOLTAGE",), "applicable_check_ids": ("VOLTAGE",),
    } | changes))
    assert project(verification=result(), check_coverage=coverage).software_checks.state is c.SoftwareCheckState.NOT_RUN


@pytest.mark.parametrize("state", [
    VerificationState.UNSUPPORTED, VerificationState.ESTIMATED, VerificationState.CONCEPTUAL,
])
def test_assessment_contract_unresolved_applicable_finding_cannot_pass(state):
    c = contract()
    finding = VerificationFinding(
        "unresolved", "VOLTAGE", state, "warning", "Check is unresolved", ("component-pump",),
    )
    assessment = project(verification=result(finding), check_coverage=covered())
    assert assessment.software_checks.state is c.SoftwareCheckState.NOT_RUN


def test_assessment_contract_unrelated_evidence_estimate_does_not_hide_software_success():
    c = contract()
    finding = VerificationFinding(
        "estimated-fact", "PROPERTY_SOURCE", VerificationState.ESTIMATED,
        "warning", "Unsourced property", ("component-pump",),
    )
    assessment = project(verification=result(finding), check_coverage=covered())
    assert assessment.software_checks.state is c.SoftwareCheckState.PASSED
    assert assessment.engineering_evidence.state is c.EngineeringEvidenceState.NOT_VERIFIED


@pytest.mark.parametrize("state", [VerificationState.CROSS_CHECKED, VerificationState.FAILED])
def test_assessment_contract_old_findings_cannot_support_current_revision(state):
    c = contract()
    old = VerificationFinding(
        "old-voltage", "VOLTAGE", state, "info", "Prior revision", ("component-pump",), revision=1,
    )
    current = VerificationFinding(
        "current-voltage", "VOLTAGE", VerificationState.CROSS_CHECKED,
        "info", "Current revision", ("component-pump",), revision=2,
    )
    assessment = project(
        assessed_revision_id="revision-2", revision_number=2,
        current_revision_id="revision-2", current_revision_number=2,
        verification=result(old, current), check_coverage=covered(),
    )
    assert assessment.freshness is c.AssessmentFreshness.CURRENT
    assert assessment.software_checks.state is c.SoftwareCheckState.STALE
    assert assessment.operational_status == "ready_with_limitations"


def test_assessment_contract_current_failure_is_not_hidden_by_old_success():
    c = contract()
    old = VerificationFinding(
        "old-voltage", "VOLTAGE", VerificationState.CROSS_CHECKED,
        "info", "Prior revision", ("component-pump",), revision=1,
    )
    current = VerificationFinding(
        "current-voltage", "VOLTAGE", VerificationState.FAILED,
        "critical", "Current voltage failure", ("component-pump",), revision=2,
    )
    assessment = project(
        assessed_revision_id="revision-2", revision_number=2,
        current_revision_id="revision-2", current_revision_number=2,
        verification=result(old, current), check_coverage=covered(),
    )
    assert assessment.software_checks.state is c.SoftwareCheckState.FAILED


@pytest.mark.parametrize("changes", [
    {"evaluation_scope": None},
    {"satisfied_count": 0},
    {"missing_count": 1},
    {"unassessed_count": 1},
])
def test_assessment_contract_rejects_unsubstantiated_fulfilled_request(changes):
    c = contract()
    with pytest.raises(ValueError):
        c.RequestAssessment(**({
            "state": c.RequestState.FULFILLED, "evaluation_scope": "declared_voltage",
            "satisfied_count": 1,
        } | changes))


def test_assessment_contract_serialization_keeps_meanings_separate():
    c = contract()
    assumption = EvidenceRecord.curated(
        "e-voltage", EvidenceKind.ENGINEERING_ASSUMPTION, "Assumed voltage",
        "https://example.test/assumption", "Planner", ("voltage_v",),
    )
    finding = VerificationFinding(
        "failure", "VOLTAGE", VerificationState.FAILED, "critical",
        "Declared voltage mismatch", ("component-pump",),
    )
    assessment = project(
        request=c.RequestAssessment(state=c.RequestState.PARTIAL, missing_count=1),
        verification=result(finding),
        property_evidence=(c.PropertyEvidence("component-pump", "voltage_v", assumption),),
        representations=(proxy(),),
    )
    payload = json.loads(json.dumps(assessment.to_dict()))
    assert payload["assessmentVersion"] == 1
    assert payload["operationalStatus"] == "ready_with_limitations"
    assert payload["request"]["state"] == "PARTIAL"
    assert payload["softwareChecks"]["state"] == "FAILED"
    assert payload["engineeringEvidence"]["state"] == "NOT_VERIFIED"
    assert payload["engineeringEvidence"]["properties"][0]["origin"] == "DECLARED"
    assert payload["representations"][0]["kind"] == "PROCEDURAL_PROXY"
    assert payload["representations"][0]["artifactState"] == "READY"
    assert payload["representations"][0]["cadEvaluationState"] == "NOT_RUN"


def test_assessment_contract_projection_and_serialization_do_not_mutate_inputs():
    c = contract()
    item = proxy()
    verification = result()
    request = c.RequestAssessment(state=c.RequestState.UNSUPPORTED, unassessed_count=1)
    before = copy.deepcopy((item, verification, request))
    assessment = project(request=request, verification=verification, representations=(item,))
    payload = assessment.to_dict()
    payload["representations"][0]["semanticIds"].clear()
    assert (item, verification, request) == before
    assert assessment.to_dict()["representations"][0]["semanticIds"] == ["component-pump"]


# Task 1.2: original text, not the planner's requirement entities, is authoritative.
from pathlib import Path
from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind, Relationship
from aura.engineering_graph.serialization import graph_from_dict


def obligations(objective):
    c = contract()
    assert hasattr(c, "collect_request_obligations"), "Original-request ledger is not implemented"
    return c.collect_request_obligations(objective)


def declared_graph(*parts):
    root = EngineeringEntity("project-test", EntityKind.PROJECT, "Arbitrary project")
    return EngineeringGraph(root.id, entities={root.id: root} | {p.id: p for p in parts})


def declared_part(id, family, **parameters):
    return EngineeringEntity(id, EntityKind.COMPONENT, "Uninformative name", "project-test",
                             {"family": family, "parameters": parameters})


def archived(slug):
    path = Path(__file__).parents[1] / "docs/audits/2026-10-05" / slug / "graph.json"
    graph = graph_from_dict(json.loads(path.read_text(encoding="utf-8")))
    return graph.entities[graph.project_id].metadata["objective"], graph


@pytest.mark.parametrize("slug,terms", [
    ("unfamiliar-lead-screw", ("slider", "400 mm", "8 mm", "stepper", "rails", "switches", "12 V")),
    ("unfamiliar-gripper", ("gripper", "60 mm", "jaws", "guides", "rack", "pinion")),
])
def test_request_obligations_archived_wrong_family_never_fulfills(slug, terms):
    c = contract()
    objective, graph = archived(slug)
    ledger = obligations(objective)
    assessment = c.assess_request(ledger, graph)
    assert assessment.state is not c.RequestState.FULFILLED
    for term in terms:
        matches = [r for r in assessment.obligations if term.lower() in r.obligation.original_text.lower()]
        assert matches, term
        assert any(r.disposition.value != "SATISFIED" for r in matches), term
    assert assessment.original_objective_digest == ledger.objective_digest


def test_request_obligations_explicit_12v_is_not_satisfied_by_default_5v():
    c = contract()
    graph = declared_graph(declared_part("power", "low_voltage_power_source", voltage_v=5))
    assessment = c.assess_request(obligations("Use a 12 V power supply."), graph)
    voltage = next(r for r in assessment.obligations if r.obligation.property_name == "voltage_v")
    assert voltage.disposition.value == "MISSING"
    assert voltage.matched_semantic_ids == ("power",)
    assert assessment.state is not c.RequestState.FULFILLED


@pytest.mark.parametrize("dimension,want", [
    ({"value": 80, "unit": "mm"}, "SATISFIED"),
    ({"value": 8, "unit": "cm"}, "SATISFIED"),
    ({"value": 80}, "UNASSESSED"),
    ({"value": 80, "unit": "V"}, "UNASSESSED"),
    ({"value": 20, "unit": "mm"}, "MISSING"),
])
def test_request_obligations_dimension_requires_value_units_and_target(dimension, want):
    c = contract()
    plate = declared_part("plate", "mounting_plate")
    plate = __import__("dataclasses").replace(plate, metadata=plate.metadata | {"dimensions": {"width": dimension}})
    motor = declared_part("motor", "small_dc_motor")
    motor = __import__("dataclasses").replace(motor, metadata=motor.metadata | {"dimensions": {"width": {"value": 80, "unit": "mm"}}})
    assessment = c.assess_request(obligations("Use a mounting plate 80 mm wide."), declared_graph(plate, motor))
    item = next(r for r in assessment.obligations if r.obligation.property_name == "width")
    assert item.disposition.value == want
    assert item.obligation.value == 80
    assert item.obligation.unit == "mm"
    assert item.obligation.target_family == "mounting_plate"
    assert "motor" not in item.matched_semantic_ids


def test_request_obligations_quantity_is_not_model_identifier():
    ledger = obligations("Use a NEMA 17 stepper motor and two limit switches.")
    stepper = next(o for o in ledger.obligations if o.kind == "component" and o.target_family == "stepper_motor")
    switches = next(o for o in ledger.obligations if o.kind == "component" and o.target_family == "limit_switch")
    assert stepper.quantity == 1
    assert switches.quantity == 2
    assert all(o.quantity != 17 for o in ledger.obligations)
    assert any("NEMA 17" in o.original_text for o in ledger.obligations)


def test_request_obligations_unknown_residual_prevents_fulfilled():
    c = contract()
    text = "Use a 12 V power supply; it must survive salt fog for ten years."
    ledger = obligations(text)
    assessment = c.assess_request(ledger, declared_graph(declared_part("power", "low_voltage_power_source", voltage_v=12)))
    assert assessment.state is not c.RequestState.FULFILLED
    unknown = [r for r in assessment.obligations if r.disposition.value == "UNASSESSED"]
    assert any("survive salt fog" in r.obligation.original_text for r in unknown)
    assert assessment.unassessed_count > 0
    for o in ledger.obligations:
        assert text[o.start:o.end] == o.original_text
        assert o.required


def test_request_obligations_scoped_match_is_not_hardware_validation():
    c = contract()
    ledger = obligations("Use two 12 V DC motors and a 12 V power supply.")
    graph = declared_graph(declared_part("m1", "small_dc_motor", voltage_v=12),
                           declared_part("m2", "small_dc_motor", voltage_v=12),
                           declared_part("power", "low_voltage_power_source", voltage_v=12))
    request = c.assess_request(ledger, graph)
    assert request.state is c.RequestState.FULFILLED
    assert request.evaluation_scope
    assert request.unassessed_count == request.missing_count == 0
    workspace = project(request=request, representations=(proxy(),), original_objective_digest=ledger.objective_digest)
    assert workspace.engineering_evidence.state is c.EngineeringEvidenceState.NOT_VERIFIED
    assert workspace.representations[0].kind is c.RepresentationKind.PROCEDURAL_PROXY
    payload = workspace.to_dict()["request"]
    assert payload["obligations"][0]["obligation"]["originalText"]
    assert payload["originalObjectiveDigest"] == ledger.objective_digest


def test_request_obligations_generated_requirements_are_not_proof():
    c = contract()
    graph = declared_graph(declared_part("servo", "servo", voltage_v=5))
    root = graph.get(graph.project_id)
    graph.entities[root.id] = __import__("dataclasses").replace(root, metadata={
        "semanticRequirements": [{"description": "12 V power supply", "satisfied": True}],
    })
    graph.entities["req"] = EngineeringEntity("req", EntityKind.REQUIREMENT, "12 V power supply", root.id,
                                               {"satisfied": True, "voltage_v": 12})
    assessment = c.assess_request(obligations("Use a 12 V power supply."), graph)
    assert assessment.state is not c.RequestState.FULFILLED
    assert not assessment.satisfied_count


@pytest.mark.parametrize("text", [
    "Use a 12 V motor or a 5 V servo.",
    "Use a motor rated at least 12 V.",
    "Use no DC motors.",
    "Use a 12 V motor with automatic obstacle avoidance.",
    "Use a 12 V motor and make it waterproof.",
])
def test_request_obligations_unsupported_language_cannot_disappear(text):
    c = contract()
    graph = declared_graph(declared_part("motor", "small_dc_motor", voltage_v=12),
                           declared_part("servo", "servo", voltage_v=5))
    assessment = c.assess_request(obligations(text), graph)
    assert assessment.state is not c.RequestState.FULFILLED
    assert assessment.unassessed_count


def test_request_obligations_relationship_requires_real_matching_endpoints():
    c = contract()
    ledger = obligations("Connect the power supply to the DC motor.")
    graph = declared_graph(declared_part("power", "low_voltage_power_source"),
                           declared_part("motor", "small_dc_motor"))
    before = c.assess_request(ledger, graph)
    assert before.state is not c.RequestState.FULFILLED
    graph.relationships["edge"] = Relationship("edge", "power", "motor", "power")
    after = c.assess_request(ledger, graph)
    assert after.state is c.RequestState.FULFILLED
    relation = next(r for r in after.obligations if r.obligation.kind == "relationship")
    assert relation.matched_semantic_ids == ("edge", "power", "motor")


def test_request_obligations_paraphrases_and_stable_spans():
    c = contract()
    text = "Include three 9 V DC motors; include a mounting plate 7 cm wide."
    first = obligations(text)
    assert first == obligations(text)
    assert first.objective_digest != obligations(text.replace("9 V", "12 V")).objective_digest
    assert any(o.quantity == 3 for o in first.obligations)
    graph = declared_graph(declared_part("m", "small_dc_motor", voltage_v=9))
    assert c.assess_request(first, graph).state is not c.RequestState.FULFILLED


def test_request_obligations_missing_numeric_property_is_not_invented():
    c = contract()
    graph = declared_graph(declared_part("power", "low_voltage_power_source"))
    assessment = c.assess_request(obligations("Use a 12 V power supply."), graph)
    item = next(r for r in assessment.obligations if r.obligation.property_name == "voltage_v")
    assert item.disposition.value == "UNASSESSED"


def test_request_obligations_ambiguous_multiple_targets_is_unassessed():
    c = contract()
    assessment = c.assess_request(obligations("Use two DC motors, one rated 5 V and the other 12 V."),
        declared_graph(declared_part("m1", "small_dc_motor", voltage_v=12),
                       declared_part("m2", "small_dc_motor", voltage_v=12)))
    assert assessment.state is not c.RequestState.FULFILLED
    assert assessment.unassessed_count


@pytest.mark.parametrize("text", [
    "Use a .5 V motor.",
    "Use a motor < 5 V.",
    "Use a motor <= 5 V.",
    "Use a motor ≥ 5 V.",
    "Use a motor 5 V ± 2 V.",
    "Use a 5 V motor wide.",
    "Use a 5 V wide motor.",
    "Use 0 DC motors.",
    "Use a DC motor and a DC motor.",
])
def test_request_obligations_review_numeric_or_quantity_cannot_false_fulfill(text):
    c = contract()
    request = c.assess_request(obligations(text), declared_graph(declared_part("motor", "small_dc_motor", voltage_v=5)))
    assert request.state is not c.RequestState.FULFILLED


@pytest.mark.parametrize("text", [
    "Connect no power supply to the DC motor.",
    "Connect only a waterproof power supply to the DC motor.",
    "Connect the power supply to the DC motor without overheating.",
])
def test_request_obligations_review_relationship_does_not_swallow_modifiers(text):
    c = contract()
    graph = declared_graph(declared_part("power", "low_voltage_power_source"), declared_part("motor", "small_dc_motor"))
    graph.relationships["edge"] = Relationship("edge", "power", "motor", "power")
    request = c.assess_request(obligations(text), graph)
    assert request.state is not c.RequestState.FULFILLED
    assert request.unassessed_count


@pytest.mark.parametrize("metadata", [
    {"family": "mounting_plate", "dimensions": None},
    {"family": "mounting_plate", "dimensions": {"width": None}},
    {"family": "mounting_plate", "dimensions": {"width": "80 mm"}},
    {"family": "small_dc_motor", "parameters": None},
    {"family": "small_dc_motor", "parameters": "5 V"},
])
def test_request_obligations_review_unusable_graph_properties_remain_unassessed(metadata):
    c = contract()
    part = EngineeringEntity("part", EntityKind.COMPONENT, "Part", "project-test", metadata)
    text = "Use a mounting plate 80 mm wide." if metadata["family"] == "mounting_plate" else "Use a 5 V DC motor."
    request = c.assess_request(obligations(text), declared_graph(part))
    assert request.state is not c.RequestState.FULFILLED
    assert request.unassessed_count


def test_request_obligations_review_fractional_value_retains_numeric_meaning():
    c = contract()
    ledger = obligations("Use a .5 V DC motor.")
    item = next(o for o in ledger.obligations if o.property_name == "voltage_v")
    assert item.value == .5
    assert item.unit == "V"
    assert c.assess_request(ledger, declared_graph(declared_part("motor", "small_dc_motor", voltage_v=.5))).state is c.RequestState.FULFILLED


def test_request_obligations_review_duplicate_components_need_distinct_semantic_ids():
    c = contract()
    ledger = obligations("Use a DC motor and a DC motor.")
    graph = declared_graph(declared_part("motor1", "small_dc_motor"), declared_part("motor2", "small_dc_motor"))
    request = c.assess_request(ledger, graph)
    assert request.state is c.RequestState.FULFILLED
    matches = [r.matched_semantic_ids for r in request.obligations if r.obligation.kind == "component"]
    assert matches == [("motor1",), ("motor2",)]


def test_request_obligations_review_generic_model_number_is_not_quantity():
    ledger = obligations("Use a NEMA 17 motor.")
    assert all(o.quantity != 17 for o in ledger.obligations)
    assert any("NEMA 17" in o.original_text for o in ledger.obligations)


def test_request_obligations_review_connection_references_do_not_add_parts():
    c = contract()
    ledger = obligations("Use a DC motor and a power supply. Connect the power supply to the DC motor.")
    graph = declared_graph(declared_part("power", "low_voltage_power_source"), declared_part("motor", "small_dc_motor"))
    graph.relationships["edge"] = Relationship("edge", "power", "motor", "power")
    assert c.assess_request(ledger, graph).state is c.RequestState.FULFILLED


def test_request_obligations_slider_carriage_is_not_a_servo_platform():
    c = contract()
    _, graph = archived("unfamiliar-lead-screw")
    text = "Use a lead screw, two linear guide rails, a carriage, a stepper motor, limit switches, 400 mm travel, and a 12 V supply."
    request = c.assess_request(obligations(text), graph)
    for family in ("lead_screw", "linear_guide", "carriage", "stepper_motor", "limit_switch"):
        item = next(r for r in request.obligations if r.obligation.kind == "component" and r.obligation.target_family == family)
        assert item.disposition is c.ObligationDisposition.MISSING
        assert not item.matched_semantic_ids
    assert any(r.obligation.value == 400 and r.obligation.unit == "mm" and r.disposition is c.ObligationDisposition.UNASSESSED
               for r in request.obligations)
    voltage = next(r for r in request.obligations if r.obligation.property_name == "voltage_v")
    assert voltage.disposition is c.ObligationDisposition.MISSING
    assert request.state is not c.RequestState.FULFILLED
