from __future__ import annotations

import json
import subprocess
import time
from hashlib import sha256
from uuid import uuid4
from dataclasses import replace
from pathlib import Path
from typing import Any

from aura.engineering_graph.model import EngineeringGraph, EntityKind
from aura.infrastructure.persistence.project_repository import ProjectRepository
from .representations import (GenerationResult, RepresentationRecord, RepresentationSpec,
    RepresentationSpecValidator, RepresentationStatus, RepresentationType)


CAD_VERSION = "2.0.6"
TSCIRCUIT_VERSION = "0.0.1609"


def representation_specs(graph: EngineeringGraph) -> list[RepresentationSpec]:
    coordinate = {"forward": "+X", "left": "+Y", "up": "+Z"}
    components=graph.find(kind=EntityKind.COMPONENT);mechanical=[]
    for entity in components:
        family=entity.metadata.get("family",entity.metadata.get("role",""));dims=entity.metadata.get("dimensions",{})
        value=lambda key,default:float(dims.get(key,{}).get("value",default))
        geometry=None
        if family in {"enclosure","mounting_plate"} or entity.id=="component-enclosure": geometry={"operation":"filleted_enclosure","width":value("width",100),"depth":value("length",80),"height":value("height",40),"radius":4}
        elif family in {"container","reservoir"} or entity.id=="component-reservoir":
            w,h=value("width",80),value("height",120);geometry={"operation":"loft","sections":[{"z":0,"radius":w*.4},{"z":h*.5,"radius":w*.5},{"z":h,"radius":w*.42}]}
        elif family in {"tube"} or entity.id=="component-tubing": geometry={"operation":"pipe","radius":5,"path":[[0,0,0],[30,0,15],[55,20,45],[85,25,80]]}
        elif family in {"lid","generic_mechanical_part"}: geometry={"operation":"box","width":value("width",60),"depth":value("length",40),"height":value("height",8)}
        if geometry: mechanical.append(RepresentationSpec(RepresentationType.MECHANICAL_3D,(entity.id,),{"units":"mm","coordinateSystem":coordinate,"geometry":geometry}))
    categories={"microcontroller_board":("U","controller",["VCC","GND","PWM1","PWM2"]),"controller":("U","controller",["VCC","GND","PWM1","PWM2"]),"temperature_sensor":("S","soil_sensor",["VCC","GND","OUT"]),"environmental_sensor":("S","soil_sensor",["VCC","GND","OUT"]),"distance_sensor":("S","soil_sensor",["VCC","GND","OUT"]),"moisture_sensor":("S","soil_sensor",["VCC","GND","OUT"]),"mosfet_driver":("Q","mosfet",["G","D","S"]),"pump switching":("Q","mosfet",["G","D","S"]),"fan":("M","motor",["+","-"]),"servo":("M","servo",["PWM","V+","GND"]),"small_dc_pump":("M","motor",["+","-"]),"water delivery":("M","motor",["+","-"]),"low_voltage_power_source":("BT","power_source",["+","-"]),"system power":("BT","power_source",["+","-"]),"indicator":("R","soil_sensor",["VCC","GND","OUT"]),"soil sensing":("S","soil_sensor",["VCC","GND","OUT"])}
    counts={};circuit_components=[];references={}
    for entity in components:
        family=entity.metadata.get("family",entity.metadata.get("role",""));category=categories.get(family)
        if not category: continue
        prefix,kind,pins=category;counts[prefix]=counts.get(prefix,0)+1;ref=f"{prefix}{counts[prefix]}";references[entity.id]=ref
        circuit_components.append({"reference":ref,"semanticId":entity.id,"kind":kind,"pins":pins})
    connections=[];unconnected=[];signal_counts={}
    pin_alias={
        "controller":{"power":"VCC","5v":"VCC","3v3":"VCC","ground":"GND","gnd":"GND","signal":"PWM1","gpio-pump":"PWM1","gpio-sensor":"PWM2"},
        "servo":{"power":"V+","ground":"GND","signal":"PWM"},
        "power_source":{"power":"+","5v":"+","ground":"-"},
        "motor":{"power":"+","power+":"+","ground":"-"},
        "mosfet":{"logic-in":"G","logic-gnd":"S","load-in":"D","load-out":"D"},
        "soil_sensor":{"power":"VCC","vcc":"VCC","ground":"GND","gnd":"GND","signal":"OUT"},
    }
    for relationship in graph.relationships.values():
        a,b=references.get(relationship.source_id),references.get(relationship.target_id)
        if not (a and b): continue
        source=next(x for x in circuit_components if x["reference"]==a);target=next(x for x in circuit_components if x["reference"]==b)
        connection_id=relationship.metadata.get("connection_id","");connection=graph.entities.get(connection_id)
        source_interface=(connection.metadata.get("source_interface") if connection else None) or ("signal" if relationship.type=="control" else relationship.type)
        target_interface=(connection.metadata.get("target_interface") if connection else None) or ("signal" if relationship.type=="control" else relationship.type)
        source_pin=pin_alias.get(source["kind"],{}).get(source_interface);target_pin=pin_alias.get(target["kind"],{}).get(target_interface)
        if source["kind"]=="controller" and target["kind"]=="servo" and relationship.type=="control":
            signal_counts[a]=signal_counts.get(a,0)+1;source_pin=f"PWM{signal_counts[a]}"
        if source_pin in source["pins"] and target_pin in target["pins"]: connections.append({"from":f"{a}.{source_pin}","to":f"{b}.{target_pin}","graphConnectionId":connection_id})
        elif relationship.type in {"power","ground","control","signal","regulated-power","switched-power"}: unconnected.append({"graphConnectionId":connection_id,"sourceSemanticId":relationship.source_id,"targetSemanticId":relationship.target_id,"reason":"no compatible electrical interface"})
    graph_ids = {entity.id for entity in graph.find(kind=EntityKind.COMPONENT)}
    if "component-reservoir" in graph_ids:
        order={"component-reservoir":0,"component-tubing":1,"component-enclosure":2};mechanical.sort(key=lambda spec:order.get(spec.semantic_ids[0],9))
    circuit = RepresentationSpec(RepresentationType.CIRCUIT_SCHEMATIC,
        tuple(dict.fromkeys(item["semanticId"] for item in circuit_components)),
        {"components": circuit_components, "connections": connections, "unconnected":unconnected})
    validator = RepresentationSpecValidator()
    return [validator.validate(spec, graph_ids) for spec in [*mechanical, circuit] if spec.semantic_ids]

irrigation_specs=representation_specs


def initial_records(project_id: str, revision: int, specs: list[RepresentationSpec]) -> list[RepresentationRecord]:
    records=[]
    for spec in specs:
        suffix = spec.semantic_ids[0].removeprefix("component-") if len(spec.semantic_ids)==1 else ("irrigation" if {"component-esp32","component-pump"}.issubset(spec.semantic_ids) else "system")
        generator, version = ("cascade-core", CAD_VERSION) if spec.kind is RepresentationType.MECHANICAL_3D else ("tscircuit", TSCIRCUIT_VERSION)
        records.append(RepresentationRecord(f"repr-{suffix}-{'3d' if spec.kind is RepresentationType.MECHANICAL_3D else 'schematic'}",
            project_id, revision, spec.semantic_ids, spec.kind, generator=generator, generator_version=version,
            verification_status="accepted",operation_id=f"representation-{sha256(f'{project_id}|{revision}|{suffix}|{spec.kind.value}'.encode()).hexdigest()[:20]}",generation=1))
    return records


class CircuitGeneratorAdapter:
    generator_name = "tscircuit"
    generator_version = TSCIRCUIT_VERSION
    MAX_OUTPUT_BYTES = 5_000_000

    def __init__(self, timeout: float = 8.0, node_executable: str = "node", script_path: Path | None = None) -> None:
        self.timeout=timeout; self.node_executable=node_executable
        self.script_path=(script_path or Path(__file__).with_name("web") / "frontend" / "generators" / "tscircuit" / "generate-circuit.mjs").resolve()

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
        return replace(self._generate_circuit(replace(stale,operation_id=f"representation-{uuid4().hex}",generation=record.generation+1), spec, artifact.artifact_id),revision=len(graph.revisions))

    def regenerate(self, graph: EngineeringGraph, record: RepresentationRecord) -> RepresentationRecord:
        """Regenerate one graph-derived representation, retaining a usable fallback on failure."""
        if record.type is RepresentationType.CIRCUIT_SCHEMATIC:
            return self.regenerate_circuit(graph, record)
        spec = next(spec for spec in irrigation_specs(graph) if spec.kind is record.type and spec.semantic_ids == record.semantic_ids)
        stale = record.transition(RepresentationStatus.STALE) if record.status is RepresentationStatus.READY else replace(record,status=RepresentationStatus.STALE)
        generating = replace(stale.transition(RepresentationStatus.GENERATING),operation_id=f"representation-{uuid4().hex}",generation=record.generation+1)
        artifact = self.repository.create_artifact(record.project_id,len(graph.revisions),list(spec.semantic_ids),spec.kind.value,"representation-spec")  # type: ignore[attr-defined]
        try:
            self.repository.write_artifact(artifact.artifact_id,json.dumps(spec.to_dict(),separators=(",", ":")).encode(),"aura-spec","1")  # type: ignore[attr-defined]
            return generating.transition(RepresentationStatus.READY,artifact_id=artifact.artifact_id,revision=len(graph.revisions),error=None)
        except Exception as exc:
            return generating.transition(RepresentationStatus.FAILED,error=str(exc)).transition(RepresentationStatus.FALLBACK,revision=len(graph.revisions))
