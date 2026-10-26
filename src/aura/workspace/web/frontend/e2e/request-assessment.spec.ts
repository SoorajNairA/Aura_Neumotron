import {expect,test} from "@playwright/test";
import {mkdirSync} from "node:fs";
import {join} from "node:path";

const backend="http://127.0.0.1:4184";
const evidence=process.env.AURA_E2E_EVIDENCE||"test-results/request-assessment";
const archived=[
 {name:"slider",objective:"Build a low-voltage motorized camera slider with 400 mm travel, an 8 mm lead screw, a NEMA 17 stepper motor, two linear guide rails, end limit switches, an Arduino Nano, and a 12 V supply."},
 {name:"gripper",objective:"Build a tabletop parallel-jaw robotic gripper with a 60 mm opening, two symmetric sliding jaws on linear guides, a servo-driven rack and pinion, an Arduino Nano, and a 5 V supply."},
];

test("keyboard users can inspect obligation and coverage details with zero findings",async({page,request})=>{
 const project=await request.post(`${backend}/api/projects`,{data:{objective:archived[0].objective,planningMode:"deterministic_test"}}).then(r=>r.json());
 // Exercise a longer supplied reason list without inventing request matching in the UI.
 project.assessment.request.reasons.push("Additional backend reason retained","Third supplied reason remains inspectable");
 await page.route(`**/api/projects/${project.projectId}`,route=>route.fulfill({json:project}));
 await page.route(`**/api/projects/${project.projectId}/verification`,route=>route.fulfill({json:{assessment:project.assessment,summary:{},findings:[]}}));
 await page.goto(`${backend}/?projectId=${project.projectId}`);await page.locator(".verify-status").click();
 const dialog=page.getByRole("dialog");const close=dialog.getByLabel("Close verification");
 await expect(close).toBeFocused();await page.keyboard.press("Tab");
 await expect(dialog.locator(".assessment-obligations > summary")).toBeFocused();
 await page.keyboard.press("Enter");await expect(dialog.locator(".assessment-obligations")).toHaveAttribute("open","");
 await page.keyboard.press("Tab");await expect(dialog.getByText("Check coverage and property origins")).toBeFocused();
 await page.keyboard.press("Enter");
 const requestReasons=dialog.locator("details section").filter({has:page.getByRole("heading",{name:"Original request: supplied reasons and scope",exact:true})});
 for(const reason of [...project.assessment.request.reasons,project.assessment.request.evaluationScope].filter(Boolean))await expect(requestReasons.getByText(reason,{exact:true})).toBeVisible();
 mkdirSync(evidence,{recursive:true});await page.screenshot({path:join(evidence,"coverage-properties.png"),fullPage:true});
 await page.keyboard.press("Tab");await expect(dialog.getByText("Assessment limitations")).toBeFocused();
 await page.keyboard.press("Tab");await expect(close).toBeFocused();
 await page.keyboard.press("Shift+Tab");await expect(dialog.getByText("Assessment limitations")).toBeFocused();
 await page.keyboard.press("Escape");await expect(dialog).toHaveCount(0);
});

for(const item of archived)test(`real archived ${item.name}: diagnostic artifacts stay selectable without verified success`,async({page,request})=>{
 mkdirSync(evidence,{recursive:true});
 const created=await request.post(`${backend}/api/projects`,{data:{objective:item.objective,planningMode:"deterministic_test"}});
 expect(created.ok()).toBeTruthy();const project=await created.json();
 expect(project.assessment.request.state).not.toBe("FULFILLED");
 const before=await request.get(`${backend}/api/projects/${project.projectId}/graph`).then(r=>r.json());
 const assembly=await request.get(`${backend}/api/projects/${project.projectId}/assembly`).then(r=>r.json());
 expect(assembly.parts.length).toBeGreaterThan(0);
 await page.goto(`${backend}/?projectId=${project.projectId}`);
 const header=page.locator(".verify-status");
 await expect(header).not.toContainText(/\bPASS\b|VERIFIED SUCCESS/i);
 await expect(header.locator("b")).not.toHaveClass(/tone-pass/);
 await header.click();
 const assessment=page.getByTestId("assessment-details").last();
 await expect(assessment.getByTestId("assessment-request")).toContainText(/partially|unsupported/i);
 await expect(assessment.getByTestId("assessment-software")).toContainText(/not run|failed|coverage unknown/i);
 await expect(assessment.getByTestId("assessment-evidence")).toContainText(/not verified|limited/i);
 await expect(assessment.getByTestId("assessment-geometry")).toContainText(/procedural concept proxy/i);
 await expect(assessment).toContainText(`Assessed revision ${project.revision}`);
 await assessment.getByText(/Missing and unassessed requirements/).click();
 const missing=project.assessment.request.obligations.find((entry:any)=>entry.disposition==="MISSING");
 await expect(assessment).toContainText(missing.obligation.originalText);
 await page.screenshot({path:join(evidence,`${item.name}-assessment.png`),fullPage:true});
 await page.getByRole("button",{name:"Close verification"}).click();
 const part=assembly.parts[0];
 await page.getByRole("button",{name:new RegExp(part.semanticId)}).first().click();
 await expect(page.getByTestId("selected")).toHaveText(part.semanticId);
 await expect(page.getByTestId("part-info")).toContainText(part.label);
 await page.getByRole("button",{name:"Split",exact:true}).click();
 await expect(page.getByTestId("schematic-camera")).toBeVisible();
 await expect(page.locator(".schematic-loading")).toHaveCount(0);
 await expect(page.getByTestId("schematic-camera").locator("svg").first()).toBeVisible();
 await expect(page.getByTestId("selected")).toHaveText(part.semanticId);
 await page.screenshot({path:join(evidence,`${item.name}-selection.png`),fullPage:true});
 await page.getByRole("button",{name:"AURA",exact:true}).click();
 await page.getByLabel("Describe an engineering system").fill(item.objective);
 await page.getByRole("button",{name:"BUILD",exact:true}).click();
 await expect(page.getByTestId("planning-origin").first()).toContainText(/deterministic/i);
 await expect(page.getByTestId("planning-origin").first()).toContainText(/reused/i);
 await expect(page.getByTestId("planning-origin").first()).not.toContainText(/live model/i);
 const after=await request.get(`${backend}/api/projects/${project.projectId}/graph`).then(r=>r.json());
 expect(after).toEqual(before);
});

test("legacy display fixture stays unknown even when old finding counters are green",async({page,request})=>{
 const created=await request.post(`${backend}/api/projects`,{data:{objective:archived[0].objective,planningMode:"deterministic_test"}});
 const project=await created.json();delete project.assessment;
 // Only the missing-assessment legacy shape is a fixture; graph/artifacts/API stay real.
 await page.route(`**/api/projects/${project.projectId}`,route=>route.fulfill({json:project}));
 await page.route(`**/api/projects/${project.projectId}/verification`,route=>route.fulfill({json:{summary:{failed:0,cross_checked:10},findings:[]}}));
 await page.goto(`${backend}/?projectId=${project.projectId}`);
 await expect(page.locator(".project-state")).toContainText("READY");
 const header=page.locator(".verify-status");await expect(header).not.toContainText(/\bPASS\b/i);
 await header.click();await expect(page.getByTestId("assessment-software").last()).toContainText(/not run|unknown/i);
 await expect(page.locator(".verification-counts")).toContainText("10");
 await page.screenshot({path:join(evidence,"legacy-unknown.png"),fullPage:true});
});

test("sanitized IAM403 create failure keeps request and retry context",async({page})=>{
 // Controlled failure response; no live-model success or credential access is implied.
 await page.route("**/api/projects",route=>route.request().method()==="POST"
  ?route.fulfill({status:503,json:{detail:{code:"IAM403",userMessage:"Provider account permission denied; Bearer invalid-browser-token api_key=invalid-browser-key"}}}):route.continue());
 await page.goto("/");const objective=page.getByLabel("Describe an engineering system");
 await objective.fill(archived[0].objective);await page.getByRole("button",{name:"BUILD",exact:true}).click();
 const error=page.getByTestId("create-error");await expect(error).toContainText("IAM403");
 await expect(error).toContainText(/account|permission/i);await expect(error).not.toContainText(/refine|mechanism/i);
 await error.getByText("Error details").click();await expect(error).not.toContainText(/invalid-browser-token|invalid-browser-key/);
 await expect(objective).toHaveValue(archived[0].objective);
 await expect(page.getByRole("button",{name:"BUILD",exact:true})).toBeEnabled();
 await page.screenshot({path:join(evidence,"provider-iam403.png"),fullPage:true});
});

for(const state of ["UNSUPPORTED","STALE"] as const)test(`${state.toLowerCase()} assessment response fixture never claims current success`,async({page,request})=>{
 const project=await request.post(`${backend}/api/projects`,{data:{objective:archived[0].objective,planningMode:"deterministic_test"}}).then(r=>r.json());
 // Projection-only state fixture; original graph and artifacts come from the real API.
 if(state==="STALE")project.assessment.freshness="STALE";
 else project.assessment.request={...project.assessment.request,state:"UNSUPPORTED",satisfiedCount:0};
 await page.route(`**/api/projects/${project.projectId}`,route=>route.fulfill({json:project}));
 await page.goto(`${backend}/?projectId=${project.projectId}`);
 const header=page.locator(".verify-status");await expect(header).toContainText(new RegExp(state,"i"));
 await expect(header.locator("b")).not.toHaveClass(/tone-pass/);
 await header.click();await expect(page.getByTestId("assessment-request").last()).toContainText(new RegExp(state,"i"));
 if(state==="STALE")await expect(page.getByTestId("assessment-details").last()).toContainText(/Assessed revision.*Stale/);
 await page.screenshot({path:join(evidence,`${state.toLowerCase()}-assessment.png`),fullPage:true});
});

test("What-If permission failure preserves target and candidate for retry",async({page,request})=>{
 const project=await request.post(`${backend}/api/projects`,{data:{objective:archived[0].objective,planningMode:"deterministic_test"}}).then(r=>r.json());
 const assembly=await request.get(`${backend}/api/projects/${project.projectId}/assembly`).then(r=>r.json());
 await page.goto(`${backend}/?projectId=${project.projectId}`);
 await page.getByRole("button",{name:new RegExp(assembly.parts[0].semanticId)}).first().click();
 await page.getByRole("button",{name:"WHAT IF?"}).click();
 await page.route(`**/api/projects/${project.projectId}/scenarios`,route=>route.fulfill({status:503,json:{detail:{code:"SCENARIO_AI_UNAVAILABLE",message:"IAM403 Permission denied"}}}));
 await page.getByLabel("Candidate engineering change").fill("Replace with another component");
 await page.getByRole("button",{name:"ANALYZE WITH AI"}).click();
 await expect(page.getByTestId("scenario-info")).toContainText("IAM403");
 await expect(page.getByTestId("scenario-info")).toContainText(/account|permission/i);
 await expect(page.getByTestId("selected")).toHaveText(assembly.parts[0].semanticId);
 await expect(page.getByRole("button",{name:"RETRY ANALYSIS"})).toBeEnabled();
 await page.screenshot({path:join(evidence,"scenario-iam403.png"),fullPage:true});
});
