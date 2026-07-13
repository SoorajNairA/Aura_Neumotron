import {expect,test} from "@playwright/test";

const enabled=process.env.AURA_RUNTIME_REHEARSAL==="1";
const base=(process.env.AURA_REHEARSAL_URL||"http://127.0.0.1:8765").replace(/\/$/,"");
const objectives=[
 "Build a quad-axis robotic manipulator",
 "Build an Arduino Nano rover with four independently driven wheels",
 "Build an automatic sliding door",
 "Build a rotating camera turntable",
 "Build a temperature-controlled vent",
 "Build a wireless two-axis greenhouse shade controller",
];

test("six-project committed-runtime rehearsal",async({page,request})=>{
 test.skip(!enabled,"Set AURA_RUNTIME_REHEARSAL=1 for the explicit release rehearsal.");
 test.setTimeout(240_000);const results:any[]=[];
 await page.goto(base);await expect(page.getByText("What do you want to build?")).toBeVisible();
 for(const [index,objective] of objectives.entries()){
  await page.getByLabel("Describe an engineering system").fill(objective);await page.getByLabel("Describe an engineering system").press("Enter");
  await expect(page.getByTestId("engineering-space")).toBeVisible({timeout:45_000});
  await expect.poll(()=>page.evaluate(()=>(window as any).__auraSceneMetrics?.()?.activeProjectId||null),{timeout:45_000}).not.toBeNull();
  const metrics=await page.evaluate(()=>(window as any).__auraSceneMetrics());
  expect(metrics.visibleMeshes).toBeGreaterThan(0);expect(metrics.finiteBounds).toBe(true);expect(metrics.contextLost).toBe(false);
  const projectId=metrics.activeProjectId,project=(await request.get(`${base}/api/projects/${projectId}`));expect(project.ok()).toBe(true);const body=await project.json();
  expect(body.status).not.toBe("build_incomplete");expect(body.revision).toBeGreaterThan(0);
  const [graph,assembly,verification]=await Promise.all([request.get(`${base}/api/projects/${projectId}/graph`).then(r=>r.json()),request.get(`${base}/api/projects/${projectId}/assembly`).then(r=>r.json()),request.get(`${base}/api/projects/${projectId}/verification`).then(r=>r.json())]);
  expect(graph.project_id).toBe(projectId);expect(assembly.parts.length).toBeGreaterThan(0);expect(assembly.unresolvedPrimaryMechanism).toEqual([]);expect(verification.summary.failed||0).toBe(0);
  await page.getByRole("button",{name:"SCHEMATIC",exact:true}).click();await expect(page.getByTestId("schematic")).toBeVisible();await expect(page.locator("[data-schematic-component-id]").first()).toBeVisible();
  await page.getByRole("button",{name:"SPLIT",exact:true}).click();await page.getByRole("button",{name:"ASSEMBLY",exact:true}).click();
  await page.locator(".semantic-parts button").first().click();await expect(page.getByTestId("selected")).not.toHaveText("");
  if(index===4){
   const sensor=page.getByRole("button",{name:/Temperature sensor component-temperature-sensor/});await sensor.click();await page.getByTestId("modification-request").fill("Turn the vent on at a lower temperature");await page.getByTestId("preview-change").click();await expect(page.getByTestId("proposal-preview")).toBeVisible();await page.getByTestId("apply-change").click();await expect(page.getByText("Revision 2",{exact:true})).toBeAttached({timeout:45_000});
   }
  const finalProject=await request.get(`${base}/api/projects/${projectId}`).then(r=>r.json());results.push({objective,projectId,revision:finalProject.revision,status:finalProject.status,planningMode:finalProject.planningMode,metrics,components:assembly.parts.length});
  if(index<objectives.length-1){await page.getByRole("button",{name:"AURA",exact:true}).click();await expect(page.getByText("What do you want to build?")).toBeVisible()}
 }
 await page.getByRole("button",{name:/PROJECT/}).click();await page.getByTestId("projects-panel").getByRole("button",{name:new RegExp(objectives[0],"i")}).click();
 await expect.poll(()=>page.evaluate(()=>(window as any).__auraSceneMetrics?.()?.activeProjectId||null)).toBe(results[0].projectId);
 console.log("AURA_RUNTIME_REHEARSAL",JSON.stringify(results));
});
