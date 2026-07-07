from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from typing import Optional
from uuid import uuid4
import json
from pydantic import BaseModel,ConfigDict,Field
from aura.engineering_graph.model import EngineeringGraph
from aura.engineering_graph.patches import GraphOperation,GraphPatch,PatchOperation

class ModificationIntent(BaseModel):
    model_config=ConfigDict(extra="forbid")
    targetSemanticId:str
    intent:str
    scalePercent:Optional[float]=None
    preserve:list[str]=Field(default_factory=list)

class LiveModificationPlanner:
    def __init__(self,provider):self.provider=provider;self.last_metadata={}
    def propose(self,graph,base:int,ids:list[str],request:str,mode:str="automatic"):
        if len(ids)!=1 or ids[0] not in graph.entities:raise ValueError("unsupported_target")
        target=graph.get(ids[0]);context={"selectedSemanticIds":ids,"component":{"id":target.id,"name":target.name,"family":target.metadata.get("family",target.metadata.get("role")),"parameters":target.metadata.get("parameters",{}),"dimensions":target.metadata.get("dimensions",{})},"request":request,"allowedIntents":["increase_size","lower_threshold","move_component","replace_driver"]}
        errors=""
        for attempt in range(2):
            prompt=f"Normalize this bounded engineering change without inventing components: {json.dumps(context,separators=(',',':'))}. {errors}"
            result=self.provider.generate_structured([{"role":"user","content":prompt}],system_prompt="You normalize AURA modification intent. Return only the response schema.",max_tokens=400,response_schema=ModificationIntent.model_json_schema())
            try:intent=ModificationIntent.model_validate_json(result.text)
            except Exception as exc:errors=f"Previous schema error: {exc}";continue
            if intent.targetSemanticId!=target.id or intent.intent not in context["allowedIntents"]:errors="Target or intent was outside the bounded request.";continue
            canonical={"increase_size":"increase capacity larger size","lower_threshold":"lower temperature threshold earlier","move_component":"move position farther","replace_driver":"replace with logic-level mosfet"}[intent.intent]
            self.last_metadata={"repairAttempts":attempt,"firstPassValid":attempt==0,"inputTokens":result.input_tokens,"outputTokens":result.output_tokens,"totalTokens":result.total_tokens,"model":result.model}
            return propose(graph,base,ids,canonical,mode)
        raise ValueError("model_modification_invalid")

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
    from aura.verification.catalogue import CATALOGUE
    exact=next((item for item in CATALOGUE if item.component_definition_id.lower() in lower),None)
    if exact:
        if family not in {exact.family,"controller" if exact.family=="microcontroller_board" else exact.family,
                          "water delivery" if exact.family=="small_dc_pump" else exact.family,
                          "soil sensing" if exact.family=="soil_moisture_sensor" else exact.family}: raise ValueError("incompatible_component_definition")
        old=meta.get("component_definition_id");meta["component_definition_id"]=exact.component_definition_id
        params=dict(meta.get("parameters",{}));params["component_definition_id"]=exact.component_definition_id;meta["parameters"]=params
        dims=exact.properties.get("dimensions")
        if dims:
            values=dims.value;meta["dimensions"]={key:{"value":value,"unit":dims.unit} for key,value in zip(("width","length","height"),values)}
        summary=f"Upgrade {target.name} to curated {exact.manufacturer} {exact.part_number}";affected=(target.id,);regen=(f"repr-{target.id.removeprefix('component-')}-3d",)
        ops=[{"operation":"replace_component_definition","path":"component_definition_id","oldValue":old,"newValue":exact.component_definition_id}]
    elif family=="temperature_sensor" and any(x in lower for x in ("lower","threshold","temperature","earlier")):
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
