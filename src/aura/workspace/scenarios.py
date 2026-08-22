from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from uuid import uuid4
from aura.engineering_graph.model import EngineeringGraph, EntityKind
from aura.engineering_graph.patches import GraphOperation,GraphPatch,PatchOperation,apply_patch
from aura.verification.service import VerificationService

class ScenarioError(ValueError):
    def __init__(self,code:str,message:str,status:int=422):super().__init__(message);self.code=code;self.message=message;self.status=status

@dataclass(frozen=True)
class EngineeringScenario:
    id:str;project_id:str;base_revision:int;base_revision_id:str|None;target_id:str;change_type:str;patch:GraphPatch;candidate_graph:EngineeringGraph;analysis:dict[str,Any]
    def to_dict(self):return {"scenarioId":self.id,"projectId":self.project_id,"baseRevision":self.base_revision,"baseRevisionId":self.base_revision_id,"targetSemanticId":self.target_id,"changeType":self.change_type,"analysis":self.analysis}

def _confidence(findings)->str:
    if any(x.severity=="critical" and x.state.value=="failed" for x in findings):return "INVALID"
    if any(x.state.value in {"failed","unsupported","conceptual"} for x in findings):return "LOW"
    if any(x.severity=="warning" or x.state.value in {"estimated","stale"} for x in findings):return "MEDIUM"
    return "HIGH"

def analyze(graph:EngineeringGraph,target_id:str,change_type:str,value:Any)->EngineeringScenario:
    if target_id not in graph.entities or graph.get(target_id).kind is not EntityKind.COMPONENT:raise ScenarioError("SCENARIO_TARGET_INVALID","What-If target must be a current component")
    target=graph.get(target_id);meta=dict(target.metadata);changes={};known=[]
    if change_type=="REPLACE_COMPONENT":
        if not isinstance(value,dict) or not str(value.get("name","")).strip():raise ScenarioError("SCENARIO_CHANGE_INVALID","Replacement name is required")
        old=target.name;params=dict(meta.get("parameters",{}));params.update({k:v for k,v in value.get("properties",{}).items() if isinstance(k,str) and isinstance(v,(str,int,float,bool))});meta["parameters"]=params
        if value.get("componentDefinitionId"):meta["component_definition_id"]=str(value["componentDefinitionId"])
        changes={"name":str(value["name"]).strip(),"metadata":meta};known.append({"kind":"KNOWN_CHANGE","message":f"{old} replaced with {changes['name']}","semanticIds":[target_id]})
    elif change_type=="MODIFY_PROPERTY":
        if not isinstance(value,dict) or not isinstance(value.get("path"),str) or value["path"] not in {"dimensions.width.value","dimensions.length.value","dimensions.height.value","parameters.voltage_v","parameters.current_a"}:raise ScenarioError("SCENARIO_CHANGE_INVALID","Property is outside the bounded What-If surface")
        path=value["path"].split(".");copy=dict(meta);cursor=copy
        for key in path[:-1]:cursor[key]=dict(cursor.get(key,{}));cursor=cursor[key]
        old=cursor.get(path[-1]);cursor[path[-1]]=value.get("value");changes={"metadata":copy};known.append({"kind":"KNOWN_CHANGE","message":f"{value['path']} changed from {old} to {value.get('value')}","semanticIds":[target_id]})
    elif change_type=="REMOVE_COMPONENT":changes={};known.append({"kind":"KNOWN_CHANGE","message":f"{target.name} removed","semanticIds":[target_id]})
    else:raise ScenarioError("SCENARIO_CHANGE_INVALID","Unsupported What-If change type")
    operation=GraphOperation(PatchOperation.REMOVE_ENTITY,target_id=target_id) if change_type=="REMOVE_COMPONENT" else GraphOperation(PatchOperation.UPDATE_ENTITY,target_id=target_id,changes=changes)
    operations=tuple(GraphOperation(PatchOperation.REMOVE_RELATIONSHIP,target_id=relation.id) for relation in graph.relationships.values() if change_type=="REMOVE_COMPONENT" and target_id in {relation.source_id,relation.target_id})+(operation,)
    patch=GraphPatch(f"scenario-patch-{uuid4().hex}",operations,f"What-If {change_type.lower().replace('_',' ')}",graph.current_revision_id)
    try:candidate=apply_patch(graph,patch)
    except Exception as exc:raise ScenarioError("SCENARIO_CANDIDATE_INVALID",str(exc)) from exc
    verification=VerificationService().verify_modification(graph,patch)
    direct={target_id};adjacent=set();relationship_changes=[]
    for relation in graph.relationships.values():
        if target_id in {relation.source_id,relation.target_id}:
            other=relation.target_id if relation.source_id==target_id else relation.source_id;adjacent.add(other);relationship_changes.append(relation.id)
    indirect=set()
    for relation in graph.relationships.values():
        if relation.source_id in adjacent:indirect.add(relation.target_id)
        if relation.target_id in adjacent:indirect.add(relation.source_id)
    indirect-=direct|adjacent
    findings=[x.to_dict() for x in verification.findings]
    derived=[{"kind":"DERIVED_IMPACT","message":f"Relationship {rid} must be re-evaluated","semanticIds":[target_id]} for rid in relationship_changes]
    uncertainty=[{"kind":"UNCERTAINTY","message":x["summary"],"semanticIds":x.get("semanticIds",[]),"findingId":x["findingId"]} for x in findings if x.get("severity") in {"WARN","FAIL"}]
    analysis={"current":{"revision":len(graph.revisions),"component":{"id":target.id,"name":target.name}},"candidate":{"component":None if change_type=="REMOVE_COMPONENT" else {"id":target.id,"name":candidate.get(target.id).name}},
        "diff":{"changedComponents":[] if change_type=="REMOVE_COMPONENT" else [target_id],"addedComponents":[],"removedComponents":[target_id] if change_type=="REMOVE_COMPONENT" else [],"changedRelationships":relationship_changes},
        "impact":{"directlyChanged":sorted(direct),"directlyAffected":sorted(adjacent),"indirectlyAffected":sorted(indirect),"affectedComponentIds":sorted((direct|adjacent|indirect)&{x.id for x in graph.find(kind=EntityKind.COMPONENT)})},
        "verification":{"accepted":verification.accepted,"state":verification.state.value,"findings":findings,"delta":verification.verification_delta},
        "confidence":_confidence(verification.findings),"explanations":[*known,*derived,*uncertainty]}
    return EngineeringScenario(f"scenario-{uuid4().hex}",graph.project_id,len(graph.revisions),graph.current_revision_id,target_id,change_type,patch,candidate,analysis)
