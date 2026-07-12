from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind
from aura.engineering_graph.interfaces import component_interfaces, interface_dict


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
    family: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"semanticId":self.semantic_id,"label":self.label,"subsystem":self.subsystem,
            "parentAssembly":self.parent,"representationSource":self.source,"dimensions":list(self.dimensions),
            "assembledTransform":{"position":list(self.assembled),"rotation":[0,0,0,1]},
            "explodedTransform":{"position":list(self.exploded),"rotation":[0,0,0,1]},
            "verificationState":self.verification,"family":self.family}


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
            parts.append(PhysicalPart(entity.id,entity.name,role,parent,source,dimensions,assembled,exploded,"conceptual",family))
    by_id={part.semantic_id:part for part in parts};interfaces=[];by_owner={}
    for entity in components:
        part=by_id[entity.id];family=entity.metadata.get("family",entity.metadata.get("role",""))
        definitions=component_interfaces(family,part.dimensions);by_owner[entity.id]=definitions
        interfaces.extend(interface_dict(entity.id,item) for item in definitions)
    positions={part.semantic_id:list(part.assembled) for part in parts};mated=[];constraints=[];used=set()
    mechanical={"mechanical","fixed","revolute","hinge"}
    for relation in graph.relationships.values():
        if relation.type not in mechanical or relation.source_id not in by_owner or relation.target_id not in by_owner: continue
        pair=next(((a,b) for a in by_owner[relation.source_id] for b in by_owner[relation.target_id]
            if b.kind in a.compatible and f"{relation.source_id}:{a.name}" not in used and f"{relation.target_id}:{b.name}" not in used),None)
        if not pair: continue
        source,target=pair;source_world=[positions[relation.source_id][i]+source.position[i] for i in range(3)]
        positions[relation.target_id]=[source_world[i]-target.position[i]+(source.axis[i] if source.axis else 0)*source.clearance_mm for i in range(3)]
        source_id=f"{relation.source_id}:{source.name}";target_id=f"{relation.target_id}:{target.name}";used.update((source_id,target_id))
        constraints.append((relation.source_id,source,relation.target_id,target))
        mated.append({"from":source_id,"to":target_id,"type":"revolute" if source.kind in {"rotating_output","hinge_axis"} else "fixed"})
    for _ in range(len(constraints)+1):
        for source_owner,source,target_owner,target in constraints:
            source_world=[positions[source_owner][i]+source.position[i] for i in range(3)]
            positions[target_owner]=[source_world[i]-target.position[i]+(source.axis[i] if source.axis else 0)*source.clearance_mm for i in range(3)]
    from dataclasses import replace
    parts=[replace(part,assembled=tuple(positions[part.semantic_id]),exploded=tuple(positions[part.semantic_id][i]+(part.exploded[i]-part.assembled[i]) for i in range(3))) for part in parts]
    return {"assemblyId":f"assembly-{graph.project_id}","units":"mm","coordinateSystem":{"forward":"+X","left":"+Y","up":"+Z"},"hierarchy":hierarchy,"parts":[p.to_dict() for p in _resolve_exploded_collisions(parts)],"interfaces":interfaces,"connectors":interfaces,"relationships":mated,"revision":len(graph.revisions),"layoutStatus":"conceptual mechanical assembly","placementMethod":"interface-frame-mating"}

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
