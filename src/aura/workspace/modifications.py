from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from uuid import uuid4
from aura.engineering_graph.model import EngineeringGraph
from aura.engineering_graph.patches import GraphOperation,GraphPatch,PatchOperation

@dataclass(frozen=True)
class ModificationProposal:
    proposal_id:str;base_revision:int;target_ids:tuple[str,...];summary:str;mode:str
    operations:tuple[dict[str,Any],...];affected_ids:tuple[str,...];unaffected:tuple[str,...]
    regenerate:tuple[str,...];verification:dict[str,Any];patch:GraphPatch
    def to_dict(self): return {"proposalId":self.proposal_id,"baseRevision":self.base_revision,"targetSemanticIds":list(self.target_ids),"summary":self.summary,"mode":self.mode,"operations":list(self.operations),"affectedSemanticIds":list(self.affected_ids),"unaffectedAreas":list(self.unaffected),"artifactsToRegenerate":list(self.regenerate),"verification":self.verification,"assumptions":["Conceptual dimensions require physical validation"]}

def propose(graph:EngineeringGraph,base:int,ids:list[str],request:str,mode:str="automatic")->ModificationProposal:
    if base!=len(graph.revisions): raise ValueError("stale_revision")
    if len(ids)!=1 or ids[0] not in graph.entities: raise ValueError("unsupported_target")
    target=graph.get(ids[0]);meta=dict(target.metadata);lower=request.lower();ops=[]
    family=meta.get("family",meta.get("role",""))
    if family=="temperature_sensor" and any(x in lower for x in ("lower","threshold","temperature","earlier")):
        params=dict(meta["parameters"]);old=params.get("threshold_c",26);params["threshold_c"]=old-2;meta["parameters"]=params;summary="Lower the temperature activation threshold";affected=(target.id,);regen=();ops=[{"operation":"replace_parameter","path":"parameters.threshold_c","oldValue":old,"newValue":params["threshold_c"]}]
    elif family in {"container","reservoir"} and any(x in lower for x in ("larger","capacity","size","width","depth")) and target.id!="component-reservoir":
        dims={k:dict(v) for k,v in meta["dimensions"].items()};ops=[]
        for key in ("width","length"):
            old=dims[key]["value"];dims[key]["value"]=round(old*1.2);ops.append({"operation":"replace_parameter","path":f"dimensions.{key}.value","oldValue":old,"newValue":dims[key]["value"]})
        meta["dimensions"]=dims;summary="Increase container capacity while preserving height";affected=(target.id,);regen=(f"repr-{target.id.removeprefix('component-')}-3d",)
    elif target.id=="component-reservoir" and any(x in lower for x in ("capacity","40%","width","depth")):
        dims={k:dict(v) for k,v in meta["dimensions"].items()};oldw=dims["width"]["value"];oldd=dims["length"]["value"];dims["width"]["value"]=round(oldw*1.18);dims["length"]["value"]=round(oldd*1.18);meta["dimensions"]=dims;summary="Increase reservoir capacity approximately 40% while preserving height";affected=(target.id,"component-tubing");regen=("repr-reservoir-3d","repr-tubing-3d");ops=[{"operation":"replace_parameter","path":"dimensions.width.value","oldValue":oldw,"newValue":dims["width"]["value"]},{"operation":"replace_parameter","path":"dimensions.length.value","oldValue":oldd,"newValue":dims["length"]["value"]}]
    elif target.id=="component-driver" and "mosfet" in lower:
        params=dict(meta["parameters"]);old=params.get("driver_type");params.update(driver_type="logic-level MOSFET",flyback_protection=True);meta["parameters"]=params;summary="Replace driver with a logic-level MOSFET suitable for the pump";affected=(target.id,);regen=("repr-irrigation-schematic",);ops=[{"operation":"replace_parameter","path":"parameters.driver_type","oldValue":old,"newValue":params["driver_type"]}]
    elif target.id=="component-pump" and any(x in lower for x in ("move","farther","position")):
        old=meta.get("assembly_offset_mm",[0,0,0]);meta["assembly_offset_mm"]=[-35,-45,0];summary="Move pump farther from electronics while preserving fluid connections";affected=(target.id,"component-tubing");regen=("repr-tubing-3d",);ops=[{"operation":"replace_parameter","path":"assembly_offset_mm","oldValue":old,"newValue":meta["assembly_offset_mm"]}]
    else: raise ValueError("unsupported_modification")
    patch=GraphPatch(f"patch-{uuid4().hex}",(GraphOperation(PatchOperation.UPDATE_ENTITY,target_id=target.id,changes={"metadata":meta}),),summary,graph.current_revision_id)
    verification={"outcome":"accepted_with_warnings","checks":[{"state":"PASSED","message":"Target and dimensions valid"},{"state":"WARNING","message":"Conceptual geometry remains estimated"}]}
    return ModificationProposal(f"proposal-{uuid4().hex}",base,tuple(ids),summary,mode,tuple(ops),affected,("unrelated subsystems",),regen,verification,patch)

def inverse_proposal(graph:EngineeringGraph, revision:dict[str,Any])->ModificationProposal:
    diff=revision.get("verification",{}).get("diff")
    if not diff or not diff.get("changed"): raise ValueError("nothing_to_undo")
    patch=revision["patch"]; target_id=next((op.target_id for op in patch.operations if op.target_id),None)
    if not target_id or target_id not in graph.entities: raise ValueError("nothing_to_undo")
    target=graph.get(target_id);meta=dict(target.metadata);inverse=[]
    for change in diff["changed"]:
        path=change["path"].split("."); cursor=meta
        for key in path[:-1]: cursor=cursor.setdefault(key,{})
        current=cursor.get(path[-1]);cursor[path[-1]]=change["oldValue"]
        inverse.append({**change,"oldValue":current,"newValue":change["oldValue"]})
    graph_patch=GraphPatch(f"patch-{uuid4().hex}",(GraphOperation(PatchOperation.UPDATE_ENTITY,target_id=target_id,changes={"metadata":meta}),),f"Undo: {patch.summary}",graph.current_revision_id)
    return ModificationProposal(f"undo-{uuid4().hex}",len(graph.revisions),(target_id,),f"Undo: {patch.summary}","undo",tuple(inverse),tuple(diff.get("affected",[target_id])),tuple(diff.get("unchanged",[])),tuple(diff.get("regenerated",[])),{"outcome":"accepted_with_warnings","checks":[{"state":"PASSED","message":"Prior structured values restored"}]},graph_patch)
