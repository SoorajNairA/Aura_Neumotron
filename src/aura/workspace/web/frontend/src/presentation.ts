export type VerificationStatus=
  |"source_verified"
  |"tool_verified"
  |"cross_checked"
  |"estimated"
  |"conceptual"
  |"failed"
  |"unsupported"
  |string;

export type WorkState="planned"|"in_progress"|"paused"|"completed"|"skipped"|"abandoned"|string;

export interface EvidencePresentation {
  evidenceId:string;
  publisher?:string;
  document?:string;
  verifiedProperty?:string;
  retrievedAt?:string;
  status?:VerificationStatus;
  sourceUrl?:string;
  details?:string;
}

export interface VerificationFindingPresentation {
  findingId:string;
  status:VerificationStatus;
  category?:string;
  summary:string;
  details?:string;
  semanticTargets:string[];
  evidenceIds:string[];
  severity?:string;
  code?:string;
}

export interface WorkHistoryEntry {
  timestamp?:string;
  fromState?:WorkState;
  toState:WorkState;
  reason?:string;
}

export interface WorkItemPresentation {
  workItemId:string;
  title:string;
  description?:string;
  state:WorkState;
  allowedTransitions:string[];
  reason?:string;
  history:WorkHistoryEntry[];
  relatedComponentIds:string[];
  relatedRequirementIds:string[];
  relatedFindingIds:string[];
}

export interface ScenarioImpactPresentation {
  scenarioId?:string;
  baseRevisionId?:string|number;
  changeSummary:string;
  changedIds:string[];
  affectedIds:string[];
  verificationBefore?:string;
  verificationAfter?:string;
  confidenceBefore?:string;
  confidenceAfter?:string;
  knownChanges:string[];
  derivedImpacts:{category?:string;summary:string;status?:string}[];
  uncertainties:string[];
  stale:boolean;
  applicable:boolean;
  compatibilityDecision?:string;
  analysisSource?:string;
}

const words=(value:unknown)=>String(value||"").trim().toLowerCase().replaceAll("-","_");

export function statusLabel(value:unknown){return words(value).replaceAll("_"," ").toUpperCase()||"UNKNOWN"}

export function statusTone(value:unknown){
  const state=words(value);
  if(["not_run","not_verified","not_assessed","unknown","stale","cad_unverified"].includes(state))return "neutral";
  if(state==="partial")return "warn";
  if(state.includes("fail")||state.includes("abandon")||state.includes("unsupported")||state.includes("incompatible")||state.includes("invalid")||state.includes("reject"))return "fail";
  if(state.includes("estimate")||state.includes("concept")||state.includes("pause")||state.includes("limit")||state.includes("warn"))return "warn";
  if(state.includes("verified")||state.includes("cross_checked")||state.includes("ready")||state.includes("complete")||state.includes("pass"))return "pass";
  return "neutral";
}

export function sanitizeDisplayText(value:unknown){
  if(typeof value!=="string")return "";
  return value.replace(/\bBearer\s+[^\s\x22\x27<>]+/gi,"Bearer [redacted]")
    .replace(/\b(?:api[_ -]?key|access[_ -]?token|authorization|password)[\x22\x27]?\s*[:=]\s*(?:\x22(?:\\.|[^\x22\\])*\x22|\x27(?:\\.|[^\x27\\])*\x27|[^\s,;&]+)/gi,"[credential redacted]")
    .replace(/\b(?:sk-[\w-]+|AIza[\w-]+|gh[pousr]_[\w]+|eyJ[\w-]+\.[\w-]+\.[\w-]+)\b/g,"[key redacted]")
    .slice(0,2000);
}

const textList=(value:unknown)=>Array.isArray(value)?value.filter(item=>typeof item==="string").map(sanitizeDisplayText):[];
const evidenceOrigin=(value:unknown)=>({DECLARED:"Declared / assumed",CURATED:"Curated reference",RETRIEVED:"Retrieved reference",MEASURED:"Measured",UNKNOWN:"Origin unknown"}[String(value)]||"Origin unknown");

/** Present backend decisions; never infer obligations or engineering validity. */
export function assessmentPresentation(raw:any,currentRevision?:number,currentRevisionId?:string){
  const valid=raw?.assessmentVersion===1&&Number.isInteger(raw.revisionNumber)&&raw.revisionNumber>0&&typeof raw.assessedRevisionId==="string"&&raw.assessedRevisionId.length>0;
  const stale=valid&&(raw.freshness==="STALE"||(currentRevision!==undefined&&raw.revisionNumber!==currentRevision)||(currentRevisionId!==undefined&&raw.assessedRevisionId!==currentRevisionId));
  const current=valid&&!stale&&raw.freshness==="CURRENT";
  const freshness=stale?"Stale":current?"Current":"Unknown";
  const result=(label:string,tone:string,reasons:string[]=[])=>({label,tone,reasons});
  const request=raw?.request,checks=raw?.softwareChecks,evidence=raw?.engineeringEvidence;
  const requestLabels:Record<string,string>={FULFILLED:"Request met within assessed scope",PARTIAL:"Request partially met",UNSUPPORTED:"Request unsupported",NEEDS_CLARIFICATION:"Request needs clarification",NOT_ASSESSED:"Request not assessed",STALE:"Request assessment stale"};
  const requestResult=current?result(requestLabels[request?.state]||"Request not assessed",request?.state==="FULFILLED"?"pass":request?.state==="UNSUPPORTED"?"fail":request?.state==="PARTIAL"?"warn":"neutral",[...textList(request?.reasons),sanitizeDisplayText(request?.evaluationScope)].filter(Boolean)):
    result(stale?"Request assessment stale":"Request not assessed",stale?"warn":"neutral",["Current original-request coverage is unavailable"]);
  const coverage=checks?.coverage;
  const coverageDetails=coverage?[
    sanitizeDisplayText(coverage.scope),
    `Ran: ${textList(coverage.executedCheckIds).join(", ")||"Unknown"}`,
    `Applicable: ${textList(coverage.applicableCheckIds).join(", ")||"Unknown"}`,
    `Not applicable: ${textList(coverage.notApplicableCheckIds).join(", ")||"None reported"}`,
    `Unevaluated: ${textList(coverage.notEvaluatedCheckIds).join(", ")||"None reported"}`,
  ]:["Execution and applicability coverage are unknown"];
  const checkPassed=current&&checks?.state==="PASSED"&&coverage?.applicabilityKnown===true;
  const software=current?result(checks?.state==="FAILED"?"Software checks failed":checkPassed?"Software checks passed within scope":"Not run / coverage unknown",checks?.state==="FAILED"?"fail":checkPassed?"pass":"neutral",textList(checks?.reasons)):
    result(stale?"Software check assessment stale":"Software checks not run / unknown","neutral",["Current execution proof is unavailable"]);
  const evidenceResult=current?result(evidence?.state==="INVALID"?"Engineering evidence invalid":evidence?.state==="LIMITED"?"Limited property evidence":"Engineering properties not verified",evidence?.state==="INVALID"?"fail":"warn",textList(evidence?.reasons)):
    result(stale?"Engineering evidence assessment stale":"Engineering evidence unknown","neutral",["No current property evidence assessment"]);
  const records=valid&&Array.isArray(raw.representations)?raw.representations.filter((item:any)=>item?.representationType==="mechanical_3d"):[];
  const proxy=records.some((item:any)=>item.kind==="PROCEDURAL_PROXY");
  const evaluated=records.length>0&&records.every((item:any)=>item.kind==="CAD_UNVERIFIED"&&item.cadEvaluationState==="SUCCEEDED");
  const geometry=current?result(proxy?"Procedural concept proxy":evaluated?"CAD evaluated; validity unverified":records.length?"CAD / 3D unverified":"3D assessment unavailable","warn",[
    proxy?"CAD is not evaluated for a concept mesh":"CAD evaluation is " +(evaluated?"reported by the backend":"not run or unconfirmed"),
    "Physical correctness is not verified",
  ]):result(stale?"3D assessment stale":"3D / CAD assessment unknown","neutral",["No current representation assessment"]);
  const origin=valid?raw.planningOrigin:undefined;
  const mode:Record<string,string>={deterministic_test:"Deterministic test",deterministic_fallback:"Deterministic fallback",live_model:"Live model"};
  const originDetails=origin?[origin.planningMode?`Planning: ${mode[origin.planningMode]||sanitizeDisplayText(origin.planningMode)}`:"",
    origin.provider?`Provider: ${sanitizeDisplayText(origin.provider)}`:"",origin.model?`Model: ${sanitizeDisplayText(origin.model)}`:"",
    origin.reusedProject===true?"Saved project reused":""].filter(Boolean):[];
  return {request:requestResult,software,evidence:evidenceResult,geometry,
    revision:valid?`Assessed revision ${raw.revisionNumber} · ${freshness}`:"Assessed revision unknown",revisionId:valid?sanitizeDisplayText(raw.assessedRevisionId):"",
    origin:originDetails.join(" · ")||"Planning origin unknown",originReason:sanitizeDisplayText(origin?.fallbackReason),
    obligations:valid&&Array.isArray(request?.obligations)?request.obligations.filter((item:any)=>["MISSING","UNASSESSED"].includes(item?.disposition)).map((item:any)=>({
      id:sanitizeDisplayText(item.obligation?.id),text:sanitizeDisplayText(item.obligation?.originalText)||"Original requirement unavailable",state:item.disposition,reason:sanitizeDisplayText(item.reason),
    })):[],
    counts:current?`${request?.satisfiedCount??"?"} met · ${request?.missingCount??"?"} missing · ${request?.unassessedCount??"?"} unassessed`:"Current requirement counts unknown",
    coverage:coverageDetails,properties:valid&&Array.isArray(evidence?.properties)?evidence.properties.map((item:any)=>({target:sanitizeDisplayText(`${item.entityId}.${item.propertyName}`),origin:evidenceOrigin(item.origin)})):[],
    representations:records.map((item:any)=>({id:sanitizeDisplayText(item.representationId),kind:item.kind==="PROCEDURAL_PROXY"?"Procedural concept proxy":item.kind==="CAD_UNVERIFIED"?"CAD unverified":"3D unknown",
      artifact:sanitizeDisplayText(item.artifactState)||"Unknown",cad:sanitizeDisplayText(item.cadEvaluationState)||"Unknown"})),
    limitations:valid?textList(raw.limitations):["Backend assessment is missing or unsupported; no engineering success is inferred"],
  };
}

export function providerErrorPresentation(payload:any,status=500){
  const detail=payload?.detail??payload;
  const text=sanitizeDisplayText(typeof detail==="string"?detail:detail?.userMessage??detail?.message??"");
  const supplied=sanitizeDisplayText(detail?.code);
  const code=/\bIAM403\b/i.test(text+supplied)?"IAM403":/^[A-Z][A-Z0-9_-]{0,79}$/.test(supplied)?supplied:`HTTP_${status}`;
  const auth=status===401||status===403||/IAM403|PERMISSION_DENIED|UNAUTHENTICATED|AUTHENTICATION|ADC\/IAM/i.test(code+" "+text);
  return {code,title:auth?"Provider account or permission issue":status===504?"Provider request timed out":"Request could not complete",
    message:auth?"Check the configured provider account and its access permissions, then retry.":text||"Retry the request or reopen the saved project.",
    details:auth?text:""};
}

export function projectStatus(project:{status?:string;capability?:{status?:string}}|undefined,verification:any){
  if(!project)return "GENERATING";
  const raw=words(project.status);
  if(raw.includes("incomplete")||raw.includes("fail"))return "BUILD INCOMPLETE";
  if(raw.includes("generat"))return "GENERATING";
  if(raw.includes("verify"))return "VERIFYING";
  const summary=verification?.summary||{};
  const limitations=Number(summary.estimated||0)+Number(summary.conceptual||0)+Number(summary.unsupported||0);
  const failed=Number(summary.failed||0);
  const capability=words(project.capability?.status);
  if(failed>0)return "READY WITH LIMITATIONS";
  if(limitations>0||capability.includes("limitation"))return "READY WITH LIMITATIONS";
  return raw.includes("ready")?"READY":statusLabel(raw);
}

export function findingPresentation(raw:any):VerificationFindingPresentation {
  return {
    findingId:String(raw?.findingId??raw?.id??"finding"),
    status:String(raw?.status??raw?.state??"unsupported"),
    category:raw?.category??raw?.domain,
    summary:String(raw?.summary??raw?.check??raw?.title??raw?.id??"Engineering finding"),
    details:sanitizeDisplayText(raw?.details??raw?.message??raw?.reason??raw?.userMessage),
    semanticTargets:[...(raw?.semanticTargets??raw?.entity_ids??raw?.entityIds??[])],
    evidenceIds:[...(raw?.evidenceIds??raw?.evidence_ids??[])],
    severity:raw?.severity??raw?.criticality,
    code:raw?.code??raw?.checkId,
  };
}

export function evidencePresentation(raw:any,id="evidence"):EvidencePresentation {
  const source=raw?.source||{};
  return {
    evidenceId:String(raw?.evidenceId??raw?.id??id),
    publisher:raw?.publisher??source?.publisher,
    document:raw?.document??raw?.title??source?.document,
    verifiedProperty:raw?.verifiedProperty??raw?.property??raw?.claim,
    retrievedAt:raw?.retrievedAt??raw?.retrieved_at??raw?.timestamp,
    status:raw?.status??raw?.state,
    sourceUrl:raw?.sourceUrl??raw?.source_url??raw?.url??source?.url,
    details:sanitizeDisplayText(raw?.details??raw?.summary??raw?.message),
  };
}

export function workItemPresentation(raw:any):WorkItemPresentation {
  return {
    workItemId:String(raw?.workItemId??raw?.id??"work-item"),
    title:String(raw?.title??"Engineering work item"),
    description:raw?.description,
    state:String(raw?.state??"planned").toLowerCase(),
    allowedTransitions:[...(raw?.allowedTransitions??raw?.allowed_transitions??[])],
    reason:raw?.reason??raw?.currentReason,
    history:[...(raw?.history??raw?.transitionHistory??[])],
    relatedComponentIds:[...(raw?.relatedComponentIds??raw?.related_component_ids??[])],
    relatedRequirementIds:[...(raw?.relatedRequirementIds??raw?.related_requirement_ids??[])],
    relatedFindingIds:[...(raw?.relatedFindingIds??raw?.related_finding_ids??[])],
  };
}

export function scenarioPresentation(raw:any):ScenarioImpactPresentation {
  const analysis=raw?.analysis??raw;
  const delta=analysis?.verification?.delta??{};
  const explanations=[...(analysis?.explanations??[])];
  return {
    scenarioId:raw?.scenarioId??raw?.id,
    baseRevisionId:raw?.baseRevisionId??raw?.base_revision_id,
    changeSummary:String(raw?.changeSummary??raw?.summary??explanations.find((item:any)=>item.kind==="KNOWN_CHANGE")?.message??"Candidate engineering change"),
    changedIds:[...(raw?.changedIds??raw?.changed_ids??analysis?.diff?.changedComponents??analysis?.diff?.removedComponents??[])],
    affectedIds:[...(raw?.affectedIds??raw?.affected_ids??analysis?.impact?.affectedComponentIds??[])],
    verificationBefore:raw?.verificationBefore??raw?.verification_before??delta?.readinessBefore,
    verificationAfter:raw?.verificationAfter??raw?.verification_after??delta?.readinessAfter,
    confidenceBefore:raw?.confidenceBefore??raw?.confidence_before,
    confidenceAfter:raw?.confidenceAfter??raw?.confidence_after??analysis?.confidence,
    knownChanges:[...(raw?.knownChanges??raw?.known_changes??explanations.filter((item:any)=>item.kind==="KNOWN_CHANGE"))],
    derivedImpacts:[...(raw?.derivedImpacts??raw?.derived_impacts??explanations.filter((item:any)=>item.kind==="DERIVED_IMPACT"))].map((impact:any)=>typeof impact==="string"?{summary:impact}:{...impact,summary:impact.summary??impact.message}),
    uncertainties:[...(raw?.uncertainties??explanations.filter((item:any)=>item.kind==="UNCERTAINTY"))].map((item:any)=>typeof item==="string"?item:String(item?.summary??item?.message??"Uncertainty")),
    stale:Boolean(raw?.stale),
    applicable:Boolean(raw?.applicable??analysis?.applicable??false),
    compatibilityDecision:analysis?.semanticAssessment?.decision,
    analysisSource:analysis?.ai?.source,
  };
}

export const requiresReason=(state:string)=>["paused","skipped","abandoned"].includes(words(state));

export function workSummary(items:WorkItemPresentation[]){
  return items.reduce<Record<string,number>>((counts,item)=>{const key=words(item.state);counts[key]=(counts[key]||0)+1;return counts},{});
}
