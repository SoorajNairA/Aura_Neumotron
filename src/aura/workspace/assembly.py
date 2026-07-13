from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
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
    rotation: tuple[float, float, float, float] = (0,0,0,1)
    verification: str = "estimated"
    family: str = ""
    transform_source: str = "INDEPENDENT_LAYOUT"

    def to_dict(self) -> dict[str, Any]:
        return {"semanticId":self.semantic_id,"label":self.label,"subsystem":self.subsystem,
            "parentAssembly":self.parent,"representationSource":self.source,"dimensions":list(self.dimensions),
            "assembledTransform":{"position":list(self.assembled),"rotation":list(self.rotation)},
            "explodedTransform":{"position":list(self.exploded),"rotation":list(self.rotation)},
            "verificationState":self.verification,"family":self.family,"transformSource":self.transform_source}


def engineering_assembly(graph:EngineeringGraph)->dict[str,Any]:
    components=graph.find(kind=EntityKind.COMPONENT);groups:dict[str,list[EngineeringEntity]]={}
    for entity in components:groups.setdefault(entity.parent_id or "conceptual",[]).append(entity)
    parts=[];hierarchy={}
    for group_index,(parent,items) in enumerate(sorted(groups.items())):
        hierarchy[parent]=[item.id for item in items]
        for index,entity in enumerate(items):
            meta=entity.metadata;family=meta.get("family",meta.get("role","generic_mechanical_part"));dims=meta.get("dimensions",{})
            dimensions=tuple(float(dims.get(key,{}).get("value",fallback)) for key,fallback in (("width",45),("length",30),("height",18)))
            role=str(meta.get("subsystem",parent.removeprefix("subsystem-")))
            # This grid is reserved for non-mechanical secondary components.
            # Mechanism members are replaced below by topology-derived roots and
            # interface-mated transforms.
            ordinal=len(parts);assembled=(220.0+(ordinal%3)*70.0,(ordinal//3)*55.0,dimensions[2]/2)
            exploded=(assembled[0]+45+(ordinal%3)*20,assembled[1]*1.35,assembled[2]+55)
            source="parametric CAD" if family in {"enclosure","container","reservoir","tube","mounting_plate","base","lid","generic_mechanical_part"} else "conceptual proxy"
            parts.append(PhysicalPart(entity.id,entity.name,role,parent,source,dimensions,assembled,exploded,(0,0,0,1),"conceptual",family))
    by_id={part.semantic_id:part for part in parts};interfaces=[];by_owner={}
    for entity in components:
        part=by_id[entity.id];family=entity.metadata.get("family",entity.metadata.get("role",""))
        definitions=component_interfaces(family,part.dimensions,entity.metadata.get("parameters",{}));by_owner[entity.id]=definitions
        interfaces.extend(interface_dict(entity.id,item) for item in definitions)
    positions={part.semantic_id:list(part.assembled) for part in parts};rotations={part.semantic_id:(0.,0.,0.,1.) for part in parts};mated=[];constraints=[];used=set();placement={part.semantic_id:"INDEPENDENT_LAYOUT" for part in parts};unresolved=[]
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
        source,target=pair
        source_id=f"{relation.source_id}:{source.name}";target_id=f"{relation.target_id}:{target.name}";used.update((source_id,target_id))
        constraints.append((relation.id,relation.source_id,source,relation.target_id,target))
        mate_type="revolute" if source.kind in {"rotating_output","hinge_axis"} else "prismatic" if source.kind=="linear_output" else "fixed"
        mated.append({"from":source_id,"to":target_id,"type":mate_type})

    # Solve the directed mate graph from deterministic structural roots.  This
    # is independent of project names, subsystem columns, or component centres.
    outgoing:dict[str,list[tuple[str,str,Any,str,Any]]]={part.semantic_id:[] for part in parts}
    incoming={part.semantic_id:0 for part in parts};undirected={part.semantic_id:set() for part in parts}
    for constraint in constraints:
        _,source_owner,_,target_owner,_=constraint
        outgoing[source_owner].append(constraint);incoming[target_owner]+=1
        undirected[source_owner].add(target_owner);undirected[target_owner].add(source_owner)
    mechanical_ids={component_id for component_id,neighbors in undirected.items() if neighbors}
    unseen=set(mechanical_ids);connected_groups=[]
    while unseen:
        seed=min(unseen);group={seed};pending=[seed];unseen.remove(seed)
        while pending:
            current=pending.pop()
            for neighbor in sorted(undirected[current] & unseen):
                unseen.remove(neighbor);group.add(neighbor);pending.append(neighbor)
        connected_groups.append(group)
    placed=set()
    for group_index,group in enumerate(sorted(connected_groups,key=lambda item:min(item))):
        roots=sorted(component_id for component_id in group if incoming[component_id]==0)
        if not roots:
            cycle=sorted(group)
            unresolved.append({"relationshipId":None,"sourceId":cycle[0],"targetId":cycle[-1],"reason":"directed mechanical mate cycle"})
            for offset,component_id in enumerate(cycle):
                positions[component_id]=[group_index*220.0,offset*70.0,by_id[component_id].dimensions[2]/2]
                placement[component_id]="CONCEPTUAL_TOPOLOGY"
            continue
        for root_index,root in enumerate(roots):
            positions[root]=[group_index*220.0,root_index*80.0,by_id[root].dimensions[2]/2]
            placement[root]="FIXED_ROOT";placed.add(root)
        pending=list(roots)
        while pending:
            source_owner=pending.pop(0)
            for _,_,source,target_owner,target in sorted(outgoing[source_owner],key=lambda item:item[0]):
                if target_owner in placed:
                    continue
                source_offset=_rotate(rotations[source_owner],source.position)
                source_world=[positions[source_owner][i]+source_offset[i] for i in range(3)]
                if source.axis and target.axis:
                    source_axis=_rotate(rotations[source_owner],source.axis)
                    desired=source_axis if source.kind in {"rotating_output","hinge_axis","linear_output"} else tuple(-value for value in source_axis)
                    rotations[target_owner]=_from_to(target.axis,desired)
                clearance=max(source.clearance_mm,target.clearance_mm)
                target_offset=_rotate(rotations[target_owner],target.position)
                positions[target_owner]=[source_world[i]-target_offset[i]+(source_axis[i] if source.axis else 0)*clearance for i in range(3)]
                placement[target_owner]="MATE_SOLVED";placed.add(target_owner);pending.append(target_owner)
        unreachable=sorted(group-placed)
        for component_id in unreachable:
            placement[component_id]="CONCEPTUAL_TOPOLOGY"
            unresolved.append({"relationshipId":None,"sourceId":roots[0],"targetId":component_id,"reason":"mate topology is not reachable from a root"})

    role_index={entity.id:set(entity.metadata.get("parameters",{}).get("functional_roles",())) for entity in components}
    parameter_index={entity.id:entity.metadata.get("parameters",{}) for entity in components}
    actuator_ids={component_id for component_id,roles in role_index.items() if "controlled_motion" in roles}
    moving_ids={component_id for component_id,roles in role_index.items() if {"moving_surface","moving_body","drive_output","motion_transmission"}&roles}
    axis_ids={component_id for component_id,parameters in parameter_index.items() if parameters.get("controlled_axis_ids") or parameters.get("driven_axis_ids")}
    primary_ids=set(axis_ids)
    for group in connected_groups:
        if (group & actuator_ids and group & moving_ids) or group & axis_ids:
            primary_ids.update(group)
    # A disconnected controlled actuator is still a primary-mechanism defect,
    # not a secondary item eligible for independent layout.
    primary_ids.update(actuator_ids)
    unresolved_primary=[]
    for component_id in sorted(primary_ids):
        if placement[component_id] in {"INDEPENDENT_LAYOUT","CONCEPTUAL_TOPOLOGY"}:
            unresolved_primary.append({"componentId":component_id,"reason":"primary mechanism lacks a root-to-mate transform"})
    from dataclasses import replace
    parts=[replace(part,assembled=tuple(positions[part.semantic_id]),exploded=tuple(positions[part.semantic_id][i]+(part.exploded[i]-part.assembled[i]) for i in range(3)),rotation=rotations[part.semantic_id],transform_source=placement[part.semantic_id]) for part in parts]
    sources=("MATE_SOLVED","FIXED_ROOT","INDEPENDENT_LAYOUT","CONCEPTUAL_TOPOLOGY","CACHED_ARTIFACT")
    source_counts={source:sum(part.transform_source==source for part in parts) for source in sources}
    return {"assemblyId":f"assembly-{graph.project_id}","units":"mm","coordinateSystem":{"forward":"+X","left":"+Y","up":"+Z"},"hierarchy":hierarchy,"parts":[p.to_dict() for p in _resolve_exploded_collisions(parts)],"interfaces":interfaces,"connectors":interfaces,"relationships":mated,"unresolvedMechanicalRelations":unresolved,"primaryMechanismIds":sorted(primary_ids),"unresolvedPrimaryMechanism":unresolved_primary,"transformSourceCounts":source_counts,"revision":len(graph.revisions),"layoutStatus":"conceptual mechanical assembly","placementMethod":"interface-frame-mating"}

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


def _rotate(q:tuple[float,float,float,float], vector:tuple[float,float,float])->tuple[float,float,float]:
    x,y,z,w=q;vx,vy,vz=vector
    tx,ty,tz=2*(y*vz-z*vy),2*(z*vx-x*vz),2*(x*vy-y*vx)
    return (vx+w*tx+y*tz-z*ty,vy+w*ty+z*tx-x*tz,vz+w*tz+x*ty-y*tx)


def _from_to(source:tuple[float,float,float],target:tuple[float,float,float])->tuple[float,float,float,float]:
    sl=max(sqrt(sum(value*value for value in source)),1e-9);tl=max(sqrt(sum(value*value for value in target)),1e-9)
    a=tuple(value/sl for value in source);b=tuple(value/tl for value in target);dot=sum(x*y for x,y in zip(a,b))
    if dot>0.999999:return (0.,0.,0.,1.)
    if dot<-.999999:
        axis=(1.,0.,0.) if abs(a[0])<.9 else (0.,1.,0.)
        cross=(a[1]*axis[2]-a[2]*axis[1],a[2]*axis[0]-a[0]*axis[2],a[0]*axis[1]-a[1]*axis[0]);length=sqrt(sum(value*value for value in cross))
        return tuple(value/length for value in cross)+(0.,)
    cross=(a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]);scale=sqrt((1+dot)*2)
    return (cross[0]/scale,cross[1]/scale,cross[2]/scale,scale/2)


def interpolate_position(part: dict[str, Any], amount: float, subsystem: str | None = None) -> tuple[float,float,float]:
    amount=max(0.0,min(1.0,amount))
    if subsystem and part["subsystem"] != subsystem: amount=0.0
    assembled=part["assembledTransform"]["position"]; exploded=part["explodedTransform"]["position"]
    return tuple(a+(b-a)*amount for a,b in zip(assembled,exploded))
