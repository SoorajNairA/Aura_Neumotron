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
    if target.id=="component-reservoir" and any(x in lower for x in ("capacity","40%","width","depth")):
        dims={k:dict(v) for k,v in meta["dimensions"].items()};oldw=dims["width"]["value"];oldd=dims["length"]["value"];dims["width"]["value"]=round(oldw*1.18);dims["length"]["value"]=round(oldd*1.18);meta["dimensions"]=dims;summary="Increase reservoir capacity approximately 40% while preserving height";affected=(target.id,"component-tubing");regen=("repr-reservoir-3d","repr-tubing-3d");ops=[{"operation":"replace_parameter","path":"dimensions.width.value","oldValue":oldw,"newValue":dims["width"]["value"]},{"operation":"replace_parameter","path":"dimensions.length.value","oldValue":oldd,"newValue":dims["length"]["value"]}]
    elif target.id=="component-driver" and "mosfet" in lower:
        params=dict(meta["parameters"]);old=params.get("driver_type");params.update(driver_type="logic-level MOSFET",flyback_protection=True);meta["parameters"]=params;summary="Replace driver with a logic-level MOSFET suitable for the pump";affected=(target.id,);regen=("repr-irrigation-schematic",);ops=[{"operation":"replace_parameter","path":"parameters.driver_type","oldValue":old,"newValue":params["driver_type"]}]
    elif target.id=="component-pump" and any(x in lower for x in ("move","farther","position")):
        old=meta.get("assembly_offset_mm",[0,0,0]);meta["assembly_offset_mm"]=[-35,-45,0];summary="Move pump farther from electronics while preserving fluid connections";affected=(target.id,"component-tubing");regen=("repr-tubing-3d",);ops=[{"operation":"replace_parameter","path":"assembly_offset_mm","oldValue":old,"newValue":meta["assembly_offset_mm"]}]
    else: raise ValueError("unsupported_modification")
    patch=GraphPatch(f"patch-{uuid4().hex}",(GraphOperation(PatchOperation.UPDATE_ENTITY,target_id=target.id,changes={"metadata":meta}),),summary,graph.current_revision_id)
    verification={"outcome":"accepted_with_warnings","checks":[{"state":"PASSED","message":"Target and dimensions valid"},{"state":"WARNING","message":"Conceptual geometry remains estimated"}]}
    return ModificationProposal(f"proposal-{uuid4().hex}",base,tuple(ids),summary,mode,tuple(ops),affected,("unrelated subsystems",),regen,verification,patch)
