from __future__ import annotations

from hashlib import sha256
import json
from dataclasses import replace

from fastapi.testclient import TestClient

from aura.workspace.server import create_app
from aura.planner.schemas import ProjectRequest
from aura.planner.service import PlannerService
from aura.verification.service import VerificationService


CASES = (
    (
        "rover",
        "Build a two-wheel remote-controlled Arduino Nano rover with a 5 V battery, motor driver, and two DC motors.",
        "Rover",
    ),
    (
        "manipulator",
        "Build a tri-axis robotic manipulator with three hobby servos.",
        "Tri-Axis Robotic Manipulator",
    ),
    (
        "sliding-door",
        "Build an automatic sliding door with a low-voltage controller.",
        "Automatic Sliding Door",
    ),
)


def _create(client: TestClient, objective: str) -> dict:
    response = client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"})
    assert response.status_code == 201, response.text
    project = response.json()
    assert project["status"] != "build_incomplete"
    return project


def _state(client: TestClient, project: dict) -> dict:
    project_id = project["projectId"]
    graph = client.get(f"/api/projects/{project_id}/graph").json()
    assembly = client.get(f"/api/projects/{project_id}/assembly").json()
    current = client.get(f"/api/projects/{project_id}").json()
    artifacts = []
    for record in current["representations"]:
        metadata = client.get(f"/api/artifacts/{record['artifactId']}").json()
        assert metadata["projectId"] == project_id
        assert metadata["revision"] == current["revision"] == record["revision"]
        artifacts.append((record["representationId"], record["artifactId"], metadata["contentHash"]))
    return {"project": current, "graph": graph, "assembly": assembly, "artifacts": artifacts}


def _fingerprint(state: dict) -> str:
    """Test-only project-level fingerprint; reusable individual templates may match."""
    graph = state["graph"]
    assembly = state["assembly"]
    payload = {
        "components": sorted((entity["id"], entity["metadata"].get("family")) for entity in graph["entities"] if entity["kind"] == "component"),
        "mates": sorted((item["from"], item["to"], item["type"]) for item in assembly["relationships"]),
        "transforms": sorted((part["semanticId"], part["assembledTransform"]["position"], part["transformSource"]) for part in assembly["parts"]),
        "mechanicalSpecs": sorted((record[0], record[2]) for record in state["artifacts"] if record[0].endswith("-3d")),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_distinct_mechanical_projects_keep_graphs_artifacts_and_assemblies_isolated(tmp_path):
    database = tmp_path / "workspace.db"
    artifacts = tmp_path / "artifacts"
    app = create_app(storage_mode="sqlite", db_path=database, artifact_dir=artifacts)
    with TestClient(app) as client:
        projects = {name: _create(client, objective) for name, objective, _ in CASES}
        states = {name: _state(client, project) for name, project in projects.items()}

        # The project records own their artifacts even where the underlying
        # bounded component template legitimately produces matching geometry.
        artifact_ids = [artifact_id for state in states.values() for _, artifact_id, _ in state["artifacts"]]
        assert len(artifact_ids) == len(set(artifact_ids))
        assert len({_fingerprint(state) for state in states.values()}) == len(CASES)

        rover = states["rover"]
        rover_mates = rover["assembly"]["relationships"]
        assert len([part for part in rover["assembly"]["parts"] if part["family"] == "small_dc_motor"]) == 2
        assert len([part for part in rover["assembly"]["parts"] if part["family"] == "drive_wheel"]) == 2
        assert sum("shaft" in mate["from"] and "hub-input" in mate["to"] for mate in rover_mates) == 2
        assert not rover["assembly"]["unresolvedMechanicalRelations"]

        manipulator = states["manipulator"]
        entities = manipulator["graph"]["entities"]
        axis_requirement = next(entity for entity in entities if entity["id"] == "requirement-controlled-axes")
        assert axis_requirement["metadata"]["required_axes"] == 3
        components = [entity for entity in entities if entity["kind"] == "component"]
        axis_ids = {axis for entity in components for axis in entity["metadata"]["parameters"].get("controlled_axis_ids", [])}
        driven_axis_ids = {axis for entity in components for axis in entity["metadata"]["parameters"].get("driven_axis_ids", [])}
        assert axis_ids == driven_axis_ids == {"axis-1", "axis-2", "axis-3"}
        assert len(manipulator["assembly"]["relationships"]) == 6
        assert manipulator["assembly"]["transformSourceCounts"]["MATE_SOLVED"] == 6
        assert not manipulator["assembly"]["unresolvedMechanicalRelations"]

        sliding = states["sliding-door"]
        sliding_mates = sliding["assembly"]["relationships"]
        assert any("linear-output" in mate["from"] and "linear-input" in mate["to"] and mate["type"] == "prismatic" for mate in sliding_mates)
        assert {part["family"] for part in sliding["assembly"]["parts"]} >= {"linear_drive", "sliding_panel"}
        assert not sliding["assembly"]["unresolvedMechanicalRelations"]

        # Repeated switching must return the same project-owned graph and
        # transforms rather than a previously loaded scene or assembly state.
        for name in ("rover", "manipulator", "sliding-door", "rover", "sliding-door", "manipulator"):
            assert _state(client, projects[name]) == states[name]
    app.state.workspace.repository.close()

    reopened = create_app(storage_mode="sqlite", db_path=database, artifact_dir=artifacts)
    with TestClient(reopened) as client:
        for name, project in projects.items():
            assert _state(client, project) == states[name]
    reopened.state.workspace.repository.close()


def test_axis_requirement_rejects_a_vague_driven_mechanism():
    plan = PlannerService().plan(ProjectRequest(
        "Tri-Axis Robotic Manipulator",
        "Build a tri-axis robotic manipulator with three hobby servos.",
        ("Provide three independent servo control channels", "Use low voltage"),
    ))
    vague = replace(plan, components=tuple(
        replace(component, parameters={key: value for key, value in component.parameters.items() if key != "driven_axis_ids"})
        for component in plan.components
    ))
    result = VerificationService().verify(vague)
    assert not result.accepted
    assert any(finding.check == "MECH_311" and finding.severity == "critical" for finding in result.findings)
