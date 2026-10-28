import {expect,test,Page} from "@playwright/test";
import {graph,mock,supported} from "./fanFixture";

const fact=(value:any,unit:string|null)=>({value,unit,evidenceId:"e",qualifier:"rated"});
const part=(componentDefinitionId:string,family:string,partNumber:string,price:any=null)=>({componentDefinitionId,family,manufacturer:"Generic",partNumber,
 properties:{supply_voltage_range:fact([3,5.5],"V"),dimensions:fact([20,10,5],"mm")},interfaces:["power","ground","signal"],evidenceIds:["e"],price});
export const catalogue=[part("ds18b20-module","temperature_sensor","DS18B20 module",{usd:3.95,source:"https://example.com",retrieved:"2026-10-27"}),
 part("dc-fan-5v","fan","5 V brushless fan"),part("resistor-4k7","resistor","4.7 kΩ resistor",{usd:0.1,source:"https://example.com",retrieved:"2026-10-27"})];

export async function openLibrary(page:Page){
 await mock(page);
 await page.route("**/api/catalogue",r=>r.fulfill({json:catalogue}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Open component library"}).click();await page.getByRole("menuitemcheckbox",{name:"Component library"}).click();
 await expect(page.getByRole("dialog",{name:"Component library"})).toBeVisible();
}

test("library opens, searches, filters and labels unpriced parts",async({page})=>{
 await openLibrary(page);
 await expect(page.getByTestId("library-row")).toHaveCount(3);
 await page.getByLabel("Search parts").fill("ds18");
 await expect(page.getByTestId("library-row")).toHaveCount(1);
 await expect(page.getByTestId("library-row")).toContainText("$3.95 · example.com (retrieved 2026-10-27)");
 await page.getByLabel("Search parts").fill("");
 await page.getByRole("group",{name:"Filter by family"}).getByRole("button",{name:"fan",exact:true}).click();
 await expect(page.getByTestId("library-row")).toHaveCount(1);
 await expect(page.getByTestId("library-row")).toContainText("price unavailable");
 await page.getByLabel("Search parts").press("Escape");
 await expect(page.getByRole("dialog",{name:"Component library"})).toHaveCount(0);
 await expect(page.getByRole("button",{name:"Open component library"})).toBeFocused();
});

const addProposal={proposalId:"proposal-add",summary:"Add DS18B20 module, 4.7 kΩ resistor",mode:"add_component",affectedSemanticIds:["component-user-a","component-user-b","component-controller"],
 unaffectedAreas:["existing components"],artifactsToRegenerate:["firmware"],
 operations:[{operation:"add_component",targetId:"component-user-a",path:"components",oldValue:null,newValue:"DS18B20 module",gpio:13,port:"signal-3"},
  {operation:"add_component",targetId:"component-user-b",path:"components",oldValue:null,newValue:"4.7 kΩ resistor",gpio:null}],
 verification:{checks:[{state:"WARNING",message:"Single signal pin assigned; bus parts (I2C/SPI) need wiring review."}]}};

test("multi-select add shows one proposal with pins and commits through the shared route",async({page})=>{
 await openLibrary(page);
 const add=page.getByRole("button",{name:/^Add \d+ to design$/});
 await expect(add).toHaveCount(0);
 await page.getByLabel("Select DS18B20 module").check();
 await page.getByLabel("Select 4.7 kΩ resistor").check();
 await expect(page.getByRole("button",{name:"Add 2 to design"})).toBeEnabled();
 await page.route("**/api/projects/project-fan/component-proposals",r=>r.fulfill({json:addProposal}));
 const posted=page.waitForRequest("**/api/projects/project-fan/component-proposals");
 await page.getByRole("button",{name:"Add 2 to design"}).click();
 expect((await posted).postDataJSON()).toEqual({baseRevision:1,componentDefinitionIds:["ds18b20-module","resistor-4k7"]});
 const preview=page.getByTestId("proposal-preview");
 await expect(preview).toContainText("DS18B20 module");
 await expect(preview).toContainText("GPIO13");
 await expect(preview).toContainText("need wiring review");
 await page.route("**/api/projects/project-fan/modification-proposals/proposal-add/commit",r=>r.fulfill({json:{projectId:"project-fan",revision:2}}));
 const committed=page.waitForRequest("**/modification-proposals/proposal-add/commit");
 await page.getByTestId("apply-change").click();
 await committed;
});

test("add errors are shown in the library",async({page})=>{
 await openLibrary(page);
 await page.route("**/api/projects/project-fan/component-proposals",r=>r.fulfill({status:409,json:{detail:{code:"NO_FREE_PIN",message:"Not enough free safe ESP32 pins for these parts."}}}));
 await page.getByLabel("Select DS18B20 module").check();
 await page.getByRole("button",{name:"Add 1 to design"}).click();
 await expect(page.getByTestId("library-error")).toContainText("Not enough free safe ESP32 pins");
});

test("code view says added parts have no generated driver",async({page})=>{
 await mock(page,{...supported,addedWithoutDriver:[{semanticId:"component-user-a",name:"DS18B20 module",port:"signal-3",gpio:13}]});
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Code",exact:true}).click();
 await expect(page.getByTestId("added-without-driver")).toContainText("DS18B20 module");
 await expect(page.getByTestId("added-without-driver")).toContainText("GPIO13");
 await expect(page.getByTestId("added-without-driver")).toContainText("Pin assigned — no generated driver yet");
});

test("part settings propose a parameter change through the proposal card",async({page})=>{
 await mock(page);
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:{...graph,entities:graph.entities.map((e:any)=>e.id==="component-temperature-sensor"?{...e,metadata:{family:"temperature_sensor",parameters:{threshold_c:26,component_definition_id:"ds18b20-module",gpio_map:{}}}}:e)}}));
 await page.route("**/api/projects/project-fan/parameter-proposals",r=>r.fulfill({json:{proposalId:"proposal-param",summary:"Set DS18B20 threshold_c to 30",mode:"parameter_change",affectedSemanticIds:["component-temperature-sensor"],unaffectedAreas:[],artifactsToRegenerate:[],
  operations:[{operation:"replace_parameter",path:"parameters.threshold_c",oldValue:26,newValue:30}],verification:{checks:[]}}}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/component-temperature-sensor/}).click();
 const settings=page.getByTestId("part-settings");
 await expect(settings.getByLabel("component_definition_id")).toHaveCount(0);
 const posted=page.waitForRequest("**/api/projects/project-fan/parameter-proposals");
 await settings.getByLabel("threshold_c").fill("30");
 await settings.getByLabel("threshold_c").press("Enter");
 expect((await posted).postDataJSON()).toEqual({baseRevision:1,componentId:"component-temperature-sensor",key:"threshold_c",value:30});
 await expect(page.getByTestId("proposal-preview")).toContainText("26 → 30");
});

async function connectSetup(page:Page,status=200,json:any={proposalId:"proposal-mount",summary:"Mount DS18B20 on ESP32 DevKit",mode:"connection",affectedSemanticIds:["component-temperature-sensor"],unaffectedAreas:[],artifactsToRegenerate:[],
  operations:[{operation:"add_mechanical_attachment",path:"mechanical attachment",oldValue:null,newValue:{sourceInterface:"mount-face-3"}}],verification:{checks:[]}}){
 await mock(page);
 await page.route("**/api/projects/project-fan/components/component-temperature-sensor/interfaces",r=>r.fulfill({json:[{name:"signal",kind:"signal_output",compatible:["electrical_connector"]},{name:"body-mount",kind:"fixed_mount",compatible:["structural_face"]}]}));
 await page.route("**/api/projects/project-fan/components/component-controller/interfaces",r=>r.fulfill({json:[{name:"mount-face-3",kind:"structural_face",compatible:["fixed_mount"]},{name:"power",kind:"electrical_power_in",compatible:["electrical_connector"]}]}));
 await page.route("**/api/projects/project-fan/connection-proposals",r=>r.fulfill({status,json}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/component-temperature-sensor/}).click();
 await page.getByRole("button",{name:"Connect…"}).click();
 await page.getByLabel("Connect from interface").selectOption("body-mount");
 await page.getByLabel("Connect to component").selectOption("component-controller");
}

test("connection tool offers only compatible interfaces and proposes the mount",async({page})=>{
 await connectSetup(page);
 const to=page.getByLabel("Connect to interface");
 await expect(to.locator("option")).toHaveText(["mount-face-3"]);
 const posted=page.waitForRequest("**/api/projects/project-fan/connection-proposals");
 await page.getByRole("button",{name:"Propose connection"}).click();
 expect((await posted).postDataJSON()).toEqual({baseRevision:1,sourceId:"component-controller",sourceInterface:"mount-face-3",targetId:"component-temperature-sensor",targetInterface:"body-mount"});
 await expect(page.getByTestId("proposal-preview")).toContainText("Mount DS18B20");
});

test("connection rejection is shown on the card",async({page})=>{
 await connectSetup(page,422,{detail:{code:"attachment_interface_in_use",message:"The selected mounting interface is already occupied by another component."}});
 await page.getByRole("button",{name:"Propose connection"}).click();
 await expect(page.getByTestId("connect-error")).toContainText("already occupied");
});

test("DS18B20 test bench shows a labelled behavioral reading; unsupported parts say so",async({page})=>{
 await mock(page);
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:{...graph,entities:graph.entities.map((e:any)=>e.id==="component-temperature-sensor"?{...e,metadata:{family:"temperature_sensor",parameters:{component_definition_id:"ds18b20-module"}}}:e)}}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/component-temperature-sensor/}).click();
 const bench=page.getByTestId("test-bench");
 await expect(bench).toContainText("Behavioral model — not hardware");
 await bench.getByLabel("Bench temperature").fill("30.03");
 await expect(bench.getByTestId("bench-reading")).toHaveText("30.0000 °C");
 await bench.getByLabel("Disconnect sensor").check();
 await expect(bench.getByTestId("bench-reading")).toContainText("-127");
 await page.getByRole("button",{name:/component-controller/}).click();
 await expect(page.getByTestId("test-bench")).toHaveCount(1);
 await expect(page.getByTestId("test-bench")).toContainText("No test bench yet");
});

test("fan test bench toggles the gate and never invents a current",async({page})=>{
 await mock(page);
 await page.route("**/api/catalogue/dc-fan-5v",r=>r.fulfill({json:{componentDefinitionId:"dc-fan-5v",family:"fan",properties:{}}}));
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:{...graph,entities:graph.entities.map((e:any)=>e.id==="component-fan"?{...e,metadata:{family:"fan",parameters:{component_definition_id:"dc-fan-5v"}}}:e)}}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/component-fan/}).click();
 const bench=page.getByTestId("test-bench");
 await expect(bench).toContainText("Stopped");
 await expect(bench).not.toContainText("current");
 await bench.getByLabel("Gate on").check();
 await expect(bench).toContainText("Running");
 await expect(bench).toContainText("current not in catalogue");
});

test("settings show only configurable keys, submit once, and reset after cancel",async({page})=>{
 await mock(page);
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:{...graph,entities:graph.entities.map((e:any)=>e.id==="component-temperature-sensor"?{...e,metadata:{family:"temperature_sensor",parameters:{threshold_c:26,max_current_a:3,flyback_protection:false,component_definition_id:"ds18b20-module"}}}:e)}}));
 let posts=0;
 await page.route("**/api/projects/project-fan/parameter-proposals",r=>{posts++;r.fulfill({json:{proposalId:"proposal-param",summary:"Set threshold",mode:"parameter_change",affectedSemanticIds:[],unaffectedAreas:[],artifactsToRegenerate:[],operations:[{path:"parameters.threshold_c",oldValue:26,newValue:30}],verification:{checks:[]}}})});
 await page.route("**/api/projects/project-fan/modification-proposals/proposal-param",r=>r.fulfill({status:204,body:""}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/component-temperature-sensor/}).click();
 const settings=page.getByTestId("part-settings");
 await expect(settings.getByLabel("max_current_a")).toHaveCount(0);
 await expect(settings.getByLabel("flyback_protection")).toHaveCount(0);
 await settings.getByLabel("threshold_c").fill("30");
 await settings.getByLabel("threshold_c").press("Enter");
 await expect(page.getByTestId("proposal-preview")).toBeVisible();
 await page.getByTestId("cancel-change").click();
 await expect(page.getByTestId("proposal-preview")).toHaveCount(0);
 await expect(settings.getByLabel("threshold_c")).toHaveValue("26");
 expect(posts).toBe(1);
});
