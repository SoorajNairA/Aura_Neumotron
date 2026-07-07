from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind


@dataclass(frozen=True)
class PhysicalPart:
    semantic_id: str
    label: str
    subsystem: str
    parent: str
    source: str
    dimensions: tuple[float, float, float]
    assembled: tuple[float, float, float]
    exploded: tuple[float, float, float]
    verification: str = "estimated"

    def to_dict(self) -> dict[str, Any]:
        return {"semanticId":self.semantic_id,"label":self.label,"subsystem":self.subsystem,
            "parentAssembly":self.parent,"representationSource":self.source,"dimensions":list(self.dimensions),
            "assembledTransform":{"position":list(self.assembled),"rotation":[0,0,0,1]},
            "explodedTransform":{"position":list(self.exploded),"rotation":[0,0,0,1]},
            "verificationState":self.verification}


CONNECTORS = [
    ("reservoir-outlet","component-reservoir","fluid_outlet",[0,32,20],[1,0,0],["fluid_inlet"]),
    ("pump-inlet","component-pump","fluid_inlet",[-18,0,8],[-1,0,0],["fluid_outlet","tube_end"]),
    ("pump-outlet","component-pump","fluid_outlet",[18,0,8],[1,0,0],["tube_end"]),
    ("tube-inlet","component-tubing","tube_end",[0,0,0],[-1,0,0],["fluid_outlet"]),
    ("tube-outlet","component-tubing","tube_end",[85,25,80],[1,0,0],["fluid_inlet"]),
    ("controller-mount","component-esp32","board_mount",[0,0,-3],[0,0,1],["electrical_mount"]),
    ("driver-mount","component-driver","board_mount",[0,0,-3],[0,0,1],["electrical_mount"]),
    ("power-mount","component-power","electrical_mount",[0,0,-8],[0,0,1],["structural_mount"]),
    ("enclosure-controller","component-enclosure","electrical_mount",[-25,5,25],[0,0,1],["board_mount"]),
    ("enclosure-driver","component-enclosure","electrical_mount",[20,-20,25],[0,0,1],["board_mount"]),
    ("enclosure-power","component-enclosure","structural_mount",[20,25,20],[0,0,1],["electrical_mount"]),
    ("enclosure-cable-exit","component-enclosure","cable_exit",[-50,0,10],[-1,0,0],["cable_exit"]),
]


RELATIONSHIPS = [
    ("reservoir-outlet","pump-inlet","fluid"),("pump-outlet","tube-inlet","fluid"),
    ("controller-mount","enclosure-controller","structural"),("driver-mount","enclosure-driver","structural"),
    ("power-mount","enclosure-power","structural"),
    ("component-esp32","component-driver","electrical"),("component-driver","component-pump","electrical"),
]


def irrigation_assembly(graph: EngineeringGraph) -> dict[str, Any]:
    if "component-reservoir" not in graph.entities or "component-pump" not in graph.entities:
        return engineering_assembly(graph)
    return _irrigation_assembly(graph)

def engineering_assembly(graph:EngineeringGraph)->dict[str,Any]:
    components=graph.find(kind=EntityKind.COMPONENT);groups:dict[str,list[EngineeringEntity]]={}
    for entity in components:groups.setdefault(entity.parent_id or "conceptual",[]).append(entity)
    parts=[];hierarchy={};columns={"electronics":70,"sensor":-40,"actuator":-130,"mechanical":-210,"power":130,"structure":0}
    for group_index,(parent,items) in enumerate(sorted(groups.items())):
        hierarchy[parent]=[item.id for item in items]
        for index,entity in enumerate(items):
            meta=entity.metadata;family=meta.get("family",meta.get("role","generic_mechanical_part"));dims=meta.get("dimensions",{})
            dimensions=tuple(float(dims.get(key,{}).get("value",fallback)) for key,fallback in (("width",45),("length",30),("height",18)))
            role=next((name for name in columns if name in (entity.parent_id or "") or name in str(meta.get("subsystem",""))),"mechanical")
            assembled=(columns[role],index*55-group_index*8,6.0);exploded=(assembled[0]*1.45,assembled[1]*1.5,assembled[2]+45+index*8)
            source="parametric CAD" if family in {"enclosure","container","reservoir","tube","mounting_plate","lid","generic_mechanical_part"} else "conceptual proxy"
            parts.append(PhysicalPart(entity.id,entity.name,role,parent,source,dimensions,assembled,exploded,"conceptual"))
    relationships=[{"from":r.source_id,"to":r.target_id,"type":r.type} for r in graph.relationships.values()]
    return {"assemblyId":f"assembly-{graph.project_id}","units":"mm","coordinateSystem":{"forward":"+X","left":"+Y","up":"+Z"},"hierarchy":hierarchy,"parts":[p.to_dict() for p in _resolve_exploded_collisions(parts)],"connectors":[],"relationships":relationships,"revision":len(graph.revisions),"layoutStatus":"conceptual"}

def _irrigation_assembly(graph: EngineeringGraph) -> dict[str, Any]:
    graph_ids={entity.id for entity in graph.find(kind=EntityKind.COMPONENT)}
    reservoir_meta=graph.get("component-reservoir").metadata
    dimensions=reservoir_meta.get("dimensions", {})
    reservoir_dimensions=tuple(float(dimensions.get(key, {}).get("value", fallback)) for key,fallback in (("width",70),("length",70),("height",150)))
    pump_offset=tuple(float(value) for value in graph.get("component-pump").metadata.get("assembly_offset_mm",[0,0,0]))
    pump_position=tuple(value+offset for value,offset in zip((-25,15,12),pump_offset))
    parts=[
        PhysicalPart("component-enclosure","Electronics enclosure","electronics","electronics-subsystem","parametric CAD",(120,100,60),(75,55,0),(145,105,45),"conceptual"),
        PhysicalPart("component-esp32","ESP32 controller","electronics","component-enclosure","conceptual proxy",(52,28,8),(50,50,34),(30,50,115)),
        PhysicalPart("component-driver","MOSFET driver","electronics","component-enclosure","conceptual proxy",(32,24,8),(95,25,34),(115,0,105)),
        PhysicalPart("component-power","Low-voltage power","electronics","component-enclosure","conceptual proxy",(48,30,18),(95,80,30),(145,125,90)),
        PhysicalPart("component-reservoir","Reservoir","water","water-subsystem","parametric CAD",reservoir_dimensions,(-105,15,0),(-210,40,20),"conceptual"),
        PhysicalPart("component-pump","DC pump","water","water-subsystem","conceptual proxy",(55,35,35),pump_position,tuple(value+offset for value,offset in zip((-35,-70,55),pump_offset))),
        PhysicalPart("component-tubing","Inlet and outlet tubing","water","water-subsystem","parametric CAD",(95,40,85),(-70,35,22),(-95,105,75),"conceptual"),
        PhysicalPart("component-sensor","Soil-moisture sensor","sensor","sensor-subsystem","conceptual proxy",(22,8,95),(175,-35,0),(235,-85,35)),
    ]
    parts=_resolve_exploded_collisions([part for part in parts if part.semantic_id in graph_ids])
    connectors=[{"connectorId":cid,"semanticId":sid,"type":kind,"localPosition":position,
        "localRotation":[0,0,0,1],"axis":axis,"withdrawalAxis":axis,"compatibleTypes":compatible}
        for cid,sid,kind,position,axis,compatible in CONNECTORS if sid in graph_ids]
    return {"assemblyId":"irrigation-system","units":"mm","coordinateSystem":{"forward":"+X","left":"+Y","up":"+Z"},
        "hierarchy":{"electronics-subsystem":["component-enclosure","component-esp32","component-driver","component-power"],
            "water-subsystem":["component-reservoir","component-pump","component-tubing"],
            "sensor-subsystem":["component-sensor"]},"parts":[part.to_dict() for part in parts],
        "connectors":connectors,"relationships":[{"from":a,"to":b,"type":kind} for a,b,kind in RELATIONSHIPS],
        "revision":len(graph.revisions)}


def _resolve_exploded_collisions(parts: list[PhysicalPart]) -> list[PhysicalPart]:
    """Deterministically extend withdrawal vectors until exploded AABBs clear."""
    from dataclasses import replace
    resolved: list[PhysicalPart]=[]
    for part in parts:
        position=list(part.exploded)
        direction=[b-a for a,b in zip(part.assembled,part.exploded)]
        for _ in range(8):
            if not any(_aabb_overlap(position,part.dimensions,list(other.exploded),other.dimensions) for other in resolved): break
            length=max(sum(value*value for value in direction)**.5,1.0)
            position=[value+axis/length*20 for value,axis in zip(position,direction)]
        resolved.append(replace(part,exploded=tuple(position)))
    return resolved


def _aabb_overlap(a:list[float],ad:tuple[float,float,float],b:list[float],bd:tuple[float,float,float])->bool:
    return all(abs(x-y)<(dx+dy)/2+8 for x,y,dx,dy in zip(a,b,ad,bd))


def interpolate_position(part: dict[str, Any], amount: float, subsystem: str | None = None) -> tuple[float,float,float]:
    amount=max(0.0,min(1.0,amount))
    if subsystem and part["subsystem"] != subsystem: amount=0.0
    assembled=part["assembledTransform"]["position"]; exploded=part["explodedTransform"]["position"]
    return tuple(a+(b-a)*amount for a,b in zip(assembled,exploded))
