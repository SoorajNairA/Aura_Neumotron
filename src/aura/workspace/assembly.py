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
    transform_source: str = "LAYOUT_FALLBACK"

    def to_dict(self) -> dict[str, Any]:
        return {"semanticId":self.semantic_id,"label":self.label,"subsystem":self.subsystem,
            "parentAssembly":self.parent,"representationSource":self.source,"dimensions":list(self.dimensions),
            "assembledTransform":{"position":list(self.assembled),"rotation":[0,0,0,1]},
            "explodedTransform":{"position":list(self.exploded),"rotation":[0,0,0,1]},
            "verificationState":self.verification,"family":self.family,"transformSource":self.transform_source}


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
    positions={part.semantic_id:list(part.assembled) for part in parts};mated=[];constraints=[];used=set();placement={part.semantic_id:"LAYOUT_FALLBACK" for part in parts};unresolved=[]
    connection_entities={entity.id:entity for entity in graph.find(kind=EntityKind.CONNECTION)}
    mechanical={"mechanical","fixed","revolute","hinge"}
    for relation in graph.relationships.values():
        if relation.type not in mechanical or relation.source_id not in by_owner or relation.target_id not in by_owner: continue
        connection=connection_entities.get(str(relation.metadata.get("connection_id","")))
        metadata=connection.metadata if connection else {}
        exact=((a,b) for a in by_owner[relation.source_id] for b in by_owner[relation.target_id]
               if a.name==metadata.get("source_interface") and b.name==metadata.get("target_interface"))
        compatible=((a,b) for a in by_owner[relation.source_id] for b in by_owner[relation.target_id] if b.kind in a.compatible)
        pair=next((candidate for candidate in (*exact,*compatible)
                   if candidate[1].kind in candidate[0].compatible and f"{relation.source_id}:{candidate[0].name}" not in used and f"{relation.target_id}:{candidate[1].name}" not in used),None)
        if not pair:
            unresolved.append({"relationshipId":relation.id,"sourceId":relation.source_id,"targetId":relation.target_id,"reason":"no unused compatible interface pair"});continue
        source,target=pair;source_world=[positions[relation.source_id][i]+source.position[i] for i in range(3)]
        positions[relation.target_id]=[source_world[i]-target.position[i]+(source.axis[i] if source.axis else 0)*source.clearance_mm for i in range(3)]
        source_id=f"{relation.source_id}:{source.name}";target_id=f"{relation.target_id}:{target.name}";used.update((source_id,target_id))
        constraints.append((relation.source_id,source,relation.target_id,target))
        placement[relation.target_id]="MATE_SOLVED"
        mate_type="revolute" if source.kind in {"rotating_output","hinge_axis"} else "prismatic" if source.kind=="linear_output" else "fixed"
        mated.append({"from":source_id,"to":target_id,"type":mate_type})
    for _ in range(len(constraints)+1):
        for source_owner,source,target_owner,target in constraints:
            source_world=[positions[source_owner][i]+source.position[i] for i in range(3)]
            positions[target_owner]=[source_world[i]-target.position[i]+(source.axis[i] if source.axis else 0)*source.clearance_mm for i in range(3)]
    from dataclasses import replace
    target_ids={target_owner for _,_,target_owner,_ in constraints}
    for source_owner,_,_,_ in constraints:
        if source_owner not in target_ids: placement[source_owner]="FIXED_DEFAULT"
    parts=[replace(part,assembled=tuple(positions[part.semantic_id]),exploded=tuple(positions[part.semantic_id][i]+(part.exploded[i]-part.assembled[i]) for i in range(3)),transform_source=placement[part.semantic_id]) for part in parts]
    source_counts={source:sum(part.transform_source==source for part in parts) for source in ("MATE_SOLVED","LAYOUT_FALLBACK","FIXED_DEFAULT")}
    return {"assemblyId":f"assembly-{graph.project_id}","units":"mm","coordinateSystem":{"forward":"+X","left":"+Y","up":"+Z"},"hierarchy":hierarchy,"parts":[p.to_dict() for p in _resolve_exploded_collisions(parts)],"interfaces":interfaces,"connectors":interfaces,"relationships":mated,"unresolvedMechanicalRelations":unresolved,"transformSourceCounts":source_counts,"revision":len(graph.revisions),"layoutStatus":"conceptual mechanical assembly","placementMethod":"interface-frame-mating"}

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
