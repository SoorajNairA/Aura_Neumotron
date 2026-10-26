import {expect,test} from "@playwright/test";
import {mkdirSync,readFileSync,writeFileSync} from "node:fs";
import {join} from "node:path";
import {randomUUID} from "node:crypto";

const archived=JSON.parse(readFileSync(new URL("../../../../../../docs/audits/2026-10-05/prompt-results.json",import.meta.url),"utf8")) as {slug:string;objective:string}[];
const backend="http://127.0.0.1:4184";
const evidence=process.env.AURA_E2E_EVIDENCE||"test-results/stage1";
const identity=(a:any)=>({state:a.request.state,revisionId:a.assessedRevisionId,revision:a.revisionNumber,freshness:a.freshness,
 satisfied:a.request.satisfiedCount,missing:a.request.missingCount,unassessed:a.request.unassessedCount,checks:a.softwareChecks,
 evidence:a.engineeringEvidence,limitations:a.limitations});

for(const original of archived)test(`Stage 1 archived ${original.slug}`,async function stage1ArchivedObjectiveGate({page,request}){
 test.setTimeout(90000);
 const out=join(evidence,original.slug);mkdirSync(out,{recursive:true});
 const save=(name:string,value:unknown)=>writeFileSync(join(out,name+".json"),JSON.stringify(value,null,2));
 const requestId=randomUUID(),operationId=randomUUID();
 save("objective",{slug:original.slug,objective:original.objective,requestId,operationId,planningMode:"deterministic_test"});
 const response=await request.post(`${backend}/api/projects`,{headers:{"X-Request-ID":requestId},data:{objective:original.objective,planningMode:"deterministic_test",operationId}});
 expect(response.status()).toBe(201);const created=await response.json();save("create",created);
 // Freshness is recorded, never invented; the isolated audit harness asserts all six initial creates are fresh.
 // Normal browser suites may already contain the same objective from another regression.
 expect(created.assessment.planningOrigin).toMatchObject({planningMode:"deterministic_test"});
 const pid=created.projectId;
 const read=async()=>{
  const project=await request.get(`${backend}/api/projects/${pid}`).then(r=>r.json());
  const listed=await request.get(`${backend}/api/projects`).then(r=>r.json()).then(values=>values.find((p:any)=>p.projectId===pid));
  const verification=await request.get(`${backend}/api/projects/${pid}/verification`).then(r=>r.json());
  for(const value of [project,listed,verification])expect(identity(value.assessment)).toEqual(identity(created.assessment));
  expect(project.assessment.request.obligations).toEqual(created.assessment.request.obligations);
  expect(verification.assessment.request.obligations).toEqual(created.assessment.request.obligations);
  expect(project.revision).toBe(created.assessment.revisionNumber);
  return {project,listed,verification};
 };
 save("initial-responses",await read());
 const graph=await request.get(`${backend}/api/projects/${pid}/graph`).then(r=>r.json());save("graph",graph);
 const assembly=await request.get(`${backend}/api/projects/${pid}/assembly`).then(r=>r.json());save("assembly",assembly);
 expect(graph.revisions.at(-1).id).toBe(created.assessment.assessedRevisionId);
 const a=created.assessment;
 if(original.slug.startsWith("unfamiliar-")){
  expect(["PARTIAL","UNSUPPORTED","NEEDS_CLARIFICATION","NOT_ASSESSED"]).toContain(a.request.state);
  expect(a.request.missingCount+a.request.unassessedCount).toBeGreaterThan(0);
 }
 expect(a.softwareChecks.coverage?.applicabilityKnown).not.toBe(true);
 expect(a.softwareChecks.state).toBe("NOT_RUN");
 expect(a.engineeringEvidence.state).not.toBe("VERIFIED");
 const mechanical=a.representations.filter((r:any)=>r.representationType==="mechanical_3d");
 expect(mechanical.length).toBeGreaterThan(0);
 for(const representation of mechanical){expect(representation.kind).toBe("PROCEDURAL_PROXY");expect(representation.cadEvaluationState).toBe("NOT_RUN")}
 expect(assembly.parts.length).toBeGreaterThan(0);
 const gaps=a.request.obligations.filter((o:any)=>["MISSING","UNASSESSED"].includes(o.disposition));
 const inspect=async()=>{
  await expect(page.locator(".project-state")).toContainText(/READY|BUILD INCOMPLETE/);
  const header=page.locator(".verify-status");await expect(header).not.toContainText(/\bPASS\b|verified success/i);
  await expect(header.locator("b")).not.toHaveClass(/tone-pass/);
  await header.click();const panel=page.getByTestId("assessment-details").last();
  await expect(panel).toContainText(`Assessed revision ${created.revision}`);
  await expect(panel.getByTestId("assessment-software")).toContainText(/not run|coverage unknown/i);
  await expect(panel.getByTestId("assessment-geometry")).toContainText("Procedural concept proxy");
  await expect(panel.getByTestId("assessment-geometry")).not.toContainText(/validated|parametric engineering/i);
  await panel.getByText(/Missing and unassessed requirements/).click();
  for(const gap of gaps)await expect(panel.locator("li b").filter({hasText:gap.obligation.originalText}).first()).toBeVisible();
  return panel;
 };
 await page.goto(`${backend}/?projectId=${pid}`);await inspect();
 await page.screenshot({path:join(out,"assessment.png"),fullPage:true});
 await page.getByLabel("Close verification").click();
 const part=assembly.parts[0];await page.getByRole("button",{name:new RegExp(part.semanticId)}).first().click();
 await expect(page.getByTestId("selected")).toHaveText(part.semanticId);
 await page.getByRole("button",{name:"Split",exact:true}).click();
 await expect(page.getByTestId("schematic-camera")).toBeVisible();
 await expect(page.locator(".schematic-loading")).toHaveCount(0);
 await expect(page.getByTestId("schematic-camera").locator("svg").first()).toBeVisible();
 await expect(page.getByTestId("selected")).toHaveText(part.semanticId);
 await page.screenshot({path:join(out,"selected-split.png"),fullPage:true});
 save("reverified-responses",await read());
 await page.reload();await inspect();
 await page.screenshot({path:join(out,"reopened.png"),fullPage:true});
 save("reopened-responses",await read());
 const cached=await request.post(`${backend}/api/projects`,{headers:{"X-Request-ID":randomUUID()},data:{objective:original.objective,planningMode:"live_model",operationId:randomUUID()}}).then(r=>r.json());
 save("cached-requesting-live",cached);
 expect(cached.projectId).toBe(pid);
 expect(cached.assessment.planningOrigin).toMatchObject({planningMode:"deterministic_test",reusedProject:true});
 expect(cached.assessment.planningOrigin.model).toBeNull();
 await page.getByLabel("Close verification").click();await page.getByRole("button",{name:"AURA",exact:true}).click();
 await page.getByLabel("Describe an engineering system").fill(original.objective);await page.getByRole("button",{name:"BUILD",exact:true}).click();
 await expect(page.getByTestId("planning-origin").first()).toContainText(/deterministic.*reused/i);
 await expect(page.getByTestId("planning-origin").first()).not.toContainText(/live model/i);
 const finalGraph=await request.get(`${backend}/api/projects/${pid}/graph`).then(r=>r.json());save("final-graph",finalGraph);
 expect(finalGraph).toEqual(graph);
 save("result",{passed:true,request:identity(a),semanticSelection:part.semanticId,planningOrigin:cached.assessment.planningOrigin});
});

test("real diagnostic schematic selection uses graph net identity and returns to the assembly",async({page,request})=>{
 const projects=await request.get(`${backend}/api/projects`).then(r=>r.json());
 const project=projects.find((p:any)=>p.objective===archived.find(o=>o.slug==="unfamiliar-lead-screw")?.objective);
 expect(project).toBeDefined();
 const graph=await request.get(`${backend}/api/projects/${project.projectId}/graph`).then(r=>r.json());
 const net=graph.entities.find((e:any)=>e.metadata?.semantic_type==="electrical_net");expect(net).toBeDefined();
 await page.goto(`${backend}/?projectId=${project.projectId}`);
 await page.getByRole("button",{name:"Split",exact:true}).click();
 await page.locator(`.schematic-nets [data-net-id="${net.id}"]`).click();
 await expect(page.getByTestId("selected")).toHaveText(net.id);
 await expect(page.getByTestId("net-info")).toContainText(net.id);
 await page.getByRole("button",{name:"SHOW ENDPOINTS IN 3D"}).click();
 await expect(page.getByTestId("engineering-space")).toHaveClass(/mode-assembly/);
 await expect(page.getByTestId("selected")).toHaveText(net.id);
 await expect(page.locator(".verify-status")).not.toContainText(/\bPASS\b/i);
 mkdirSync(evidence,{recursive:true});await page.screenshot({path:join(evidence,"diagnostic-net-selection.png"),fullPage:true});
});
