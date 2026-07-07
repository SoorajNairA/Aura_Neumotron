from __future__ import annotations

import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from aura.engineering_graph.model import EngineeringGraph, EntityKind
from aura.infrastructure.persistence.project_repository import ProjectRepository
from .representations import (GenerationResult, RepresentationRecord, RepresentationSpec,
    RepresentationSpecValidator, RepresentationStatus, RepresentationType)


CAD_VERSION = "2.0.6"
TSCIRCUIT_VERSION = "0.0.1609"


def irrigation_specs(graph: EngineeringGraph) -> list[RepresentationSpec]:
    coordinate = {"forward": "+X", "left": "+Y", "up": "+Z"}
    mechanical = [
        RepresentationSpec(RepresentationType.MECHANICAL_3D, ("component-reservoir",), {"units":"mm","coordinateSystem":coordinate,
            "geometry":{"operation":"loft","sections":[{"z":0,"radius":22},{"z":45,"radius":35},{"z":110,"radius":28},{"z":150,"radius":14}]}}),
        RepresentationSpec(RepresentationType.MECHANICAL_3D, ("component-tubing",), {"units":"mm","coordinateSystem":coordinate,
            "geometry":{"operation":"pipe","radius":5,"path":[[0,0,0],[30,0,15],[55,20,45],[85,25,80]]}}),
        RepresentationSpec(RepresentationType.MECHANICAL_3D, ("component-enclosure",), {"units":"mm","coordinateSystem":coordinate,
            "geometry":{"operation":"filleted_enclosure","width":100,"depth":120,"height":60,"radius":6}}),
    ]
    circuit_components = [
        {"reference":"U1","semanticId":"component-esp32","kind":"controller","pins":["VCC","GND","GPIO"]},
        {"reference":"S1","semanticId":"component-sensor","kind":"soil_sensor","pins":["VCC","GND","OUT"]},
        {"reference":"Q1","semanticId":"component-driver","kind":"mosfet","pins":["G","D","S"]},
        {"reference":"D1","semanticId":"component-driver","kind":"diode","pins":["A","K"]},
        {"reference":"M1","semanticId":"component-pump","kind":"motor","pins":["+","-"]},
        {"reference":"BT1","semanticId":"component-power","kind":"power_source","pins":["+","-"]},
    ]
    connections = [{"from":a,"to":b} for a,b in (("BT1.+","U1.VCC"),("BT1.-","U1.GND"),("S1.OUT","U1.GPIO"),
        ("U1.GPIO","Q1.G"),("Q1.D","M1.-"),("M1.+","BT1.+"),("D1.A","Q1.D"),("D1.K","BT1.+"),("Q1.S","BT1.-"))]
    circuit = RepresentationSpec(RepresentationType.CIRCUIT_SCHEMATIC,
        tuple(dict.fromkeys(item["semanticId"] for item in circuit_components)),
        {"components": circuit_components, "connections": connections})
    graph_ids = {entity.id for entity in graph.find(kind=EntityKind.COMPONENT)}
    validator = RepresentationSpecValidator()
    return [validator.validate(spec, graph_ids) for spec in [*mechanical, circuit]]


def initial_records(project_id: str, revision: int, specs: list[RepresentationSpec]) -> list[RepresentationRecord]:
    records=[]
    for spec in specs:
        suffix = spec.semantic_ids[0].removeprefix("component-") if len(spec.semantic_ids)==1 else "irrigation"
        generator, version = ("cascade-core", CAD_VERSION) if spec.kind is RepresentationType.MECHANICAL_3D else ("tscircuit", TSCIRCUIT_VERSION)
        records.append(RepresentationRecord(f"repr-{suffix}-{'3d' if spec.kind is RepresentationType.MECHANICAL_3D else 'schematic'}",
            project_id, revision, spec.semantic_ids, spec.kind, generator=generator, generator_version=version,
            verification_status="accepted"))
    return records


class CircuitGeneratorAdapter:
    generator_name = "tscircuit"
    generator_version = TSCIRCUIT_VERSION
    MAX_OUTPUT_BYTES = 5_000_000

    def __init__(self, timeout: float = 8.0, node_executable: str = "node", script_path: Path | None = None) -> None:
        self.timeout=timeout; self.node_executable=node_executable
        self.script_path=(script_path or Path(__file__).with_name("representation_runtime") / "generate-circuit.mjs").resolve()

    def can_generate(self, spec: RepresentationSpec) -> bool: return spec.kind is RepresentationType.CIRCUIT_SCHEMATIC

    def generate(self, spec: RepresentationSpec) -> GenerationResult:
        if not self.can_generate(spec): raise ValueError("Unsupported representation spec")
        started=time.perf_counter()
        try:
            completed=subprocess.run([self.node_executable, str(self.script_path)], input=json.dumps(spec.payload), text=True,
                capture_output=True, timeout=self.timeout, check=False, shell=False)
        except subprocess.TimeoutExpired as exc: raise TimeoutError(f"tscircuit generation exceeded {self.timeout}s") from exc
        if completed.returncode != 0: raise RuntimeError(f"tscircuit failed: {completed.stderr[:1000]}")
        if len(completed.stdout.encode()) > self.MAX_OUTPUT_BYTES: raise RuntimeError("tscircuit output exceeded limit")
        try: output=json.loads(completed.stdout)
        except json.JSONDecodeError as exc: raise RuntimeError("tscircuit returned malformed JSON") from exc
        if output.get("status") != "ready" or not isinstance(output.get("circuitJson"), list): raise RuntimeError("tscircuit returned an invalid result")
        metrics={key:float(value) for key,value in output.get("metrics",{}).items()}; metrics["totalRequestMs"]=(time.perf_counter()-started)*1000
        return GenerationResult(RepresentationStatus.READY, json.dumps(output["circuitJson"],separators=(",", ":")).encode(),
            dict(output.get("semanticMapping",{})), tuple(output.get("warnings",[])), metrics, "circuit-json")


class RepresentationService:
    def __init__(self, repository: ProjectRepository, circuit_generator: CircuitGeneratorAdapter | None = None) -> None:
        self.repository=repository; self.circuit_generator=circuit_generator or CircuitGeneratorAdapter()

    def persist_specs(self, project_id: str, revision: int, records: list[RepresentationRecord], specs: list[RepresentationSpec]) -> list[RepresentationRecord]:
        updated=[]
        for record,spec in zip(records,specs):
            artifact=self.repository.create_artifact(project_id,revision,list(spec.semantic_ids),spec.kind.value,
                "representation-spec" if spec.kind is RepresentationType.MECHANICAL_3D else "circuit-json")  # type: ignore[attr-defined]
            if spec.kind is RepresentationType.MECHANICAL_3D:
                self.repository.write_artifact(artifact.artifact_id,json.dumps(spec.to_dict(),separators=(",", ":")).encode(),"aura-spec","1")  # type: ignore[attr-defined]
                updated.append(replace(record,artifact_id=artifact.artifact_id))
            else: updated.append(self._generate_circuit(record,spec,artifact.artifact_id))
        return updated

    def _generate_circuit(self, record: RepresentationRecord, spec: RepresentationSpec, artifact_id: str) -> RepresentationRecord:
        generating=record.transition(RepresentationStatus.GENERATING)
        try:
            result=self.circuit_generator.generate(spec)
            self.repository.write_artifact(artifact_id,result.artifact or b"[]",self.circuit_generator.generator_name,self.circuit_generator.generator_version)  # type: ignore[attr-defined]
            return generating.transition(RepresentationStatus.READY,artifact_id=artifact_id,error=None)
        except Exception as exc:
            return generating.transition(RepresentationStatus.FAILED,error=str(exc)).transition(RepresentationStatus.FALLBACK)

    def regenerate_circuit(self, graph: EngineeringGraph, record: RepresentationRecord) -> RepresentationRecord:
        spec=next(spec for spec in irrigation_specs(graph) if spec.kind is RepresentationType.CIRCUIT_SCHEMATIC)
        stale=record.transition(RepresentationStatus.STALE) if record.status is RepresentationStatus.READY else replace(record,status=RepresentationStatus.STALE)
        artifact=self.repository.create_artifact(record.project_id,len(graph.revisions),list(spec.semantic_ids),spec.kind.value,"circuit-json")  # type: ignore[attr-defined]
        return self._generate_circuit(stale, spec, artifact.artifact_id)
