import {describe,expect,it} from "vitest";
import * as presentation from "./presentation";

const assess=(raw:any,revision=2,id="revision-2")=>{
 expect((presentation as any).assessmentPresentation,"Assessment display contract is missing").toBeTypeOf("function");
 return (presentation as any).assessmentPresentation(raw,revision,id);
};
const failure=(raw:any,status=503)=>{
 expect((presentation as any).providerErrorPresentation,"Provider error display contract is missing").toBeTypeOf("function");
 return (presentation as any).providerErrorPresentation(raw,status);
};
const snapshot=():any=>({assessmentVersion:1,assessedRevisionId:"revision-2",revisionNumber:2,freshness:"CURRENT",
 request:{state:"PARTIAL",satisfiedCount:1,missingCount:1,unassessedCount:1,evaluationScope:"Declared graph constraints only",reasons:["Function is not validated"],obligations:[
  {obligation:{id:"screw",originalText:"8 mm lead screw",required:true},disposition:"MISSING",reason:"No declared lead screw"},
  {obligation:{id:"opening",originalText:"60 mm opening",required:true},disposition:"UNASSESSED",reason:"Opening cannot be compared"}]},
 softwareChecks:{state:"NOT_RUN",coverage:null,reasons:["Execution coverage is unknown"]},
 engineeringEvidence:{state:"NOT_VERIFIED",properties:[{entityId:"motor",propertyName:"voltage_v",origin:"DECLARED"}],reasons:["Declared rating only"]},
 representations:[{representationId:"motor-3d",representationType:"mechanical_3d",semanticIds:["motor"],kind:"PROCEDURAL_PROXY",artifactState:"READY",cadEvaluationState:"NOT_RUN"}],
 planningOrigin:{provider:"deterministic",model:null,planningMode:"deterministic_test",reusedProject:true},limitations:["Physical correctness is not verified"]});

describe("revision-bound assessment presentation",()=>{
 it.each([undefined,null,{}, {assessmentVersion:99}])("keeps missing or legacy proof unknown (%j)",raw=>{
  const result=assess(raw);
  expect(result.request.tone).not.toBe("pass");
  expect(result.software.label).toMatch(/not run|unknown/i);
  expect(result.evidence.tone).not.toBe("pass");
  expect(result.geometry.tone).not.toBe("pass");
  expect(result.origin).not.toMatch(/live|model:/i);
 });
 it("keeps request gaps and their original text inspectable independently of readiness",()=>{
  const result=assess(snapshot());
  expect(result.request.label).toMatch(/partially/i);
  expect(result.request.tone).toBe("warn");
  expect(result.obligations).toEqual([
   {id:"screw",text:"8 mm lead screw",state:"MISSING",reason:"No declared lead screw"},
   {id:"opening",text:"60 mm opening",state:"UNASSESSED",reason:"Opening cannot be compared"}]);
  expect(presentation.projectStatus({status:"ready"},{summary:{failed:0}})).toBe("READY");
 });
 it("cannot turn an unsupported request into green success",()=>{
  const raw=snapshot();raw.request.state="UNSUPPORTED";
  expect(assess(raw).request).toMatchObject({tone:"fail"});
  expect(assess(raw).request.label).toMatch(/unsupported/i);
 });
 it.each(["STALE","UNKNOWN"])("does not present %s proof as current",freshness=>{
  const raw=snapshot();raw.freshness=freshness;raw.request.state="FULFILLED";
  expect(assess(raw).request.tone).not.toBe("pass");
  expect(assess(raw).revision).toMatch(new RegExp(freshness,"i"));
 });
 it("guards against an old revision even when the payload says CURRENT",()=>{
  const raw=snapshot();raw.revisionNumber=1;raw.assessedRevisionId="revision-1";raw.request.state="FULFILLED";
  const result=assess(raw);
  expect(result.revision).toMatch(/revision 1.*stale/i);
  expect(result.request.tone).not.toBe("pass");
 });
 it("guards against a different revision UUID at the same revision number",()=>{
  const raw=snapshot();raw.request.state="FULFILLED";
  expect(assess(raw,2,"another-revision").request.tone).not.toBe("pass");
 });
 it("distinguishes known execution from missing applicability coverage",()=>{
  const raw=snapshot();raw.softwareChecks.coverage={scope:"Graph schema and dispatch",applicabilityKnown:false,executedCheckIds:["GRAPH_SCHEMA"],applicableCheckIds:["GRAPH_SCHEMA"],notApplicableCheckIds:[],notEvaluatedCheckIds:["RULE_APPLICABILITY"]} as any;
  const result=assess(raw);
  expect(result.software.label).toMatch(/not run|coverage unknown/i);
  expect(result.coverage).toContain("Ran: GRAPH_SCHEMA");
  expect(result.coverage).toContain("Unevaluated: RULE_APPLICABILITY");
  expect(result.software.tone).not.toBe("pass");
 });
 it("displays a known check failure while the project remains operationally ready",()=>{
  const raw=snapshot();raw.softwareChecks.state="FAILED";
  expect(assess(raw).software).toMatchObject({tone:"fail"});
 });
 it("presents only the supplied fulfilled scope, without inferring engineering validity",()=>{
  const raw=snapshot();raw.request.state="FULFILLED";raw.request.missingCount=raw.request.unassessedCount=0;raw.request.obligations=[];
  const result=assess(raw);
  expect(result.request.label).toMatch(/met.*scope/i);
  expect(result.request.reasons).toContain("Declared graph constraints only");
  expect(result.evidence.tone).not.toBe("pass");
  expect(result.geometry.tone).not.toBe("pass");
 });
 it("never labels a READY procedural proxy as evaluated CAD",()=>{
  const result=assess(snapshot());
  expect(result.geometry.label).toMatch(/procedural concept proxy/i);
  expect(result.geometry.label).not.toMatch(/validated|parametric engineering/i);
  expect(result.geometry.reasons.join(" ")).toMatch(/CAD.*not evaluated|CAD.*not run/i);
  expect(result.geometry.tone).not.toBe("pass");
 });
 it("keeps an evaluated CAD artifact distinct from engineering validation",()=>{
  const raw=snapshot();raw.representations[0].kind="CAD_UNVERIFIED";raw.representations[0].cadEvaluationState="SUCCEEDED";
  const result=assess(raw);
  expect(result.geometry.label).toMatch(/CAD evaluated/i);
  expect(result.geometry.reasons.join(" ")).toMatch(/physical.*not verified/i);
  expect(result.geometry.tone).not.toBe("pass");
 });
 it("keeps declared properties distinct from retrieved or measured evidence",()=>{
  const result=assess(snapshot());
  expect(result.properties).toEqual([{target:"motor.voltage_v",origin:"Declared / assumed"}]);
  expect(result.evidence.label).toMatch(/not verified/i);
  expect(result.evidence.tone).not.toBe("pass");
 });
 it("uses known original provider/model and shows cached deterministic reuse",()=>{
  const raw=snapshot();
  expect(assess(raw).origin).toMatch(/deterministic.*reused/i);
  expect(assess(raw).origin).not.toMatch(/live|model:/i);
  raw.planningOrigin={provider:"nebius",model:"known-model",planningMode:"live_model",reusedProject:false};
  expect(assess(raw).origin).toMatch(/nebius.*known-model/i);
 });
 it.each(["NOT_RUN","NOT_VERIFIED","NOT_ASSESSED","STALE","PARTIAL","CAD_UNVERIFIED"])("never gives %s a success tone",state=>{
  expect(presentation.statusTone(state)).not.toBe("pass");
 });
});

describe("sanitized provider error presentation",()=>{
 it.each(["IAM403 {'api-key': 'invalid-quoted-key'}",JSON.stringify({api_key:"invalid-quoted-key"}),JSON.stringify({api_key:'invalid-quoted-key\\"continued-secret'})])("redacts quoted credential fields (%s)",message=>{
  expect(JSON.stringify(failure({detail:{message}}))).not.toMatch(/invalid-quoted-key|continued-secret/);
 });
 it("redacts credentials from displayed finding and evidence details",()=>{
  const text="Permission error Bearer detail-secret api_key=detail-key";
  expect(presentation.findingPresentation({message:text}).details).not.toMatch(/detail-secret|detail-key/);
  expect(presentation.evidencePresentation({details:text}).details).not.toMatch(/detail-secret|detail-key/);
 });
 it("explains IAM403 as account/permission failure and preserves the useful code",()=>{
  const result=failure({detail:{code:"SCENARIO_AI_UNAVAILABLE",message:"IAM403 Permission denied. Authorization: Bearer secret-token-value api_key=hidden-key-value"}});
  expect(result.code).toBe("IAM403");
  expect(result.title+result.message).toMatch(/account|permission/i);
  expect(JSON.stringify(result)).not.toMatch(/secret-token-value|hidden-key-value|refine|mechanism/i);
 });
 it.each([401,403])("keeps HTTP %s authentication failures actionable",status=>{
  expect(failure({},status).title).toMatch(/account|permission/i);
 });
 it("preserves sanitized structured timeout detail and code",()=>{
  const result=failure({detail:{code:"SCENARIO_AI_TIMEOUT",userMessage:"Provider request timed out; retry later."}},504);
  expect(result.code).toBe("SCENARIO_AI_TIMEOUT");
  expect(result.message).toMatch(/retry/i);
 });
 it("keeps unknown server failure unknown rather than inventing mechanism advice",()=>{
  const result=failure({},500);
  expect(result.code).toBe("HTTP_500");
  expect(result.message).not.toMatch(/refine|mechanism/i);
 });
 it("redacts common keys and bearer tokens even in a plain-string detail",()=>{
  const result=failure({detail:"IAM403 Bearer unlabelled-secret apiKey: key-secret password='hidden-password' sk-testsecret12345"});
  expect(JSON.stringify(result)).not.toMatch(/unlabelled-secret|key-secret|hidden-password|sk-testsecret12345/);
 });
});
