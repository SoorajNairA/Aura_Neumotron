import { expect,test } from "@playwright/test"
test.beforeEach(async({page})=>{page.on("pageerror",error=>console.error("PAGE_ERROR",error.message));page.on("console",message=>{if(message.type()==="error")console.error("BROWSER_ERROR",message.text())})})

const circuit=[{type:"schematic_component",schematic_component_id:"schematic_Q1",source_component_id:"source_Q1",center:{x:0,y:0},size:{width:1.5,height:.8},symbol_name:"boxresistor_right",symbol_display_value:"Q1",is_box_with_pins:true,rotation:0,aura_semantic_id:"component-driver"}]
const mechanical={representationId:"repr-reservoir-3d",projectId:"project-test",revision:1,semanticIds:["component-reservoir"],type:"mechanical_3d",status:"requested",generator:"cascade-core",generatorVersion:"2.0.6",artifactId:"artifact-spec",fallbackType:"placeholder",verificationStatus:"accepted",error:null}
const schematic={representationId:"repr-irrigation-schematic",projectId:"project-test",revision:1,semanticIds:["component-driver"],type:"circuit_schematic",status:"ready",generator:"tscircuit",generatorVersion:"0.0.1609",artifactId:"artifact-circuit",fallbackType:"placeholder",verificationStatus:"accepted",error:null}

test("does not lazy-load OpenCascade for circuit-only projects",async({page})=>{
  const requests:string[]=[];page.on("request",request=>requests.push(request.url()))
  await page.route("**/api/projects/project-test",route=>route.fulfill({json:{representations:[schematic]}}));await page.route("**/api/artifacts/artifact-circuit/content",route=>route.fulfill({json:circuit}))
  await page.goto("/?projectId=project-test");await expect(page.getByTestId("schematic")).toBeVisible();await page.getByRole("button",{name:/Q1/}).click();await expect(page.getByTestId("selected")).toHaveText("component-driver");expect(requests.some(url=>url.includes("cascadestudio.wasm")||url.includes("cascade-worker"))).toBe(false)
})

test("mechanical request lazy-loads CAD and reaches ready",async({page})=>{
  const states:string[]=[];await page.route("**/api/projects/project-test",route=>route.fulfill({json:{representations:[mechanical,schematic]}}));await page.route("**/api/artifacts/artifact-circuit/content",route=>route.fulfill({json:circuit}));await page.route("**/api/artifacts/artifact-spec/content",route=>route.fulfill({json:{kind:"mechanical_3d",semanticIds:["component-reservoir"],units:"mm",coordinateSystem:{forward:"+X",left:"+Y",up:"+Z"},geometry:{operation:"loft",sections:[{z:0,radius:20},{z:50,radius:30},{z:90,radius:12}]}}}));await page.route("**/status",async route=>{states.push((await route.request().postDataJSON()).status);await route.fulfill({json:{}})})
  await page.goto("/?projectId=project-test");await expect(page.getByText("Mechanical representations ready")).toBeVisible({timeout:35_000});expect(states).toEqual(["generating","ready"]);await page.getByRole("button",{name:/component-reservoir/}).click();await expect(page.getByTestId("selected")).toHaveText("component-reservoir")
})

test("retains a visible semantic proxy when CAD initialization fails",async({page})=>{
  await page.route("**/api/projects/project-test",route=>route.fulfill({json:{representations:[mechanical]}}));await page.route("**/cascadestudio.wasm",route=>route.abort("failed"))
  await page.goto("/?projectId=project-test");await expect(page.getByText(/CAD failed.*semantic proxies retained/)).toBeVisible({timeout:35_000});await expect(page.getByRole("button",{name:/component-reservoir/})).toBeVisible()
})
