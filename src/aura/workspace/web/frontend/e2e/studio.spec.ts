import {expect,test} from "@playwright/test";
import {LABEL,graph,mock,parts,project,rows,supported} from "./fanFixture";

test("studio top bar shows spaces, the device entry point and the planning model",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 for(const name of ["Design","Code","Simulation","Build"])await expect(page.getByRole("button",{name,exact:true})).toBeEnabled();
 await page.route("**/api/hardware/ports",r=>r.fulfill({json:{ports:[],toolchainMissing:null}}));
 const connect=page.getByRole("button",{name:"Connect device"});
 await expect(connect).toBeEnabled();await connect.click();await expect(page.getByTestId("build-view")).toBeVisible();
 await page.getByRole("button",{name:"Design",exact:true}).click();
 await expect(page.getByTestId("model-badge")).toHaveText("Nemotron · Nebius");
 await expect(page.getByTestId("breadcrumb")).toContainText("Workspace");
});

test("design view switch and code space",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Wiring",exact:true}).click();await expect(page.getByTestId("schematic")).toBeVisible();
 await page.getByRole("button",{name:"3D view",exact:true}).click();await expect(page.getByTestId("schematic")).toHaveCount(0);
 await page.getByRole("button",{name:"Code",exact:true}).click();await expect(page.getByTestId("code-view")).toBeVisible();
 await page.getByRole("button",{name:"Settings"}).click();await page.getByRole("menuitem",{name:"Work items"}).click();
 await expect(page.getByTestId("work-view")).toBeVisible();
});

test("settings menu starts a new design from an open project",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Settings"}).click();await page.getByRole("menuitem",{name:"New design"}).click();
 await expect(page.getByRole("heading",{name:"What do you want to build?"})).toBeVisible();
 await expect(page.getByLabel("Describe an engineering system")).toBeVisible();
 expect(new URL(page.url()).searchParams.get("projectId")).toBeNull();
});

test("component rail groups parts, searches and links to checks",async({page})=>{
 await mock(page);
 await page.route("**/api/projects/project-fan/verification",r=>r.fulfill({json:{state:"warning",summary:{},findings:[{findingId:"w1",check:"assembly",status:"estimated",severity:"WARN",summary:"Physical wiring unverified",semanticIds:["component-fan"]},{findingId:"w2",check:"catalogue",status:"source_verified",severity:"INFO",summary:"Datasheet",semanticIds:["component-temperature-sensor"]}]}}));
 await page.goto("/?projectId=project-fan");
 await expect(page.getByText("ENGINEERING PROJECT")).toBeVisible();
 await expect(page.getByRole("heading",{name:"Desk fan",level:1})).toBeVisible();
 await expect(page.getByTestId("rail-group-Controller")).toContainText("1");
 await expect(page.getByTestId("rail-group-Sensors")).toContainText("1");
 await expect(page.getByTestId("rail-group-Actuators")).toContainText("2");
 await page.getByTestId("rail-search").fill("fan");
 await expect(page.getByRole("button",{name:/component-/})).toHaveCount(1);
 await page.getByTestId("rail-search").fill("");
 await page.getByRole("button",{name:/Desk fan component-fan/}).click();
 await expect(page.getByTestId("selected")).toHaveText("component-fan");
 await expect(page.getByRole("button",{name:"Add component"})).toBeDisabled();
 await expect(page.getByTestId("checks-card")).toContainText("1 check needs attention");
 await page.getByTestId("checks-card").click();
 await expect(page.getByLabel("Close verification")).toBeVisible();
});

test("component rail handles an empty build",async({page})=>{
 await mock(page);
 await page.route("**/api/projects/project-fan/assembly",r=>r.fulfill({json:{parts:[],connectors:[],relationships:[]}}));
 await page.goto("/?projectId=project-fan");
 await expect(page.getByText("No components yet")).toBeVisible();
});

const conn=(source_id:string,source_interface:string,target_id:string,target_interface:string,connection_type:string)=>({id:`c-${source_id}-${target_id}-${connection_type}`,kind:"connection",name:"c",metadata:{source_id,target_id,source_interface,target_interface,connection_type}});
const pinGraph={project_id:"project-fan",entities:[{id:"project-fan",kind:"project",name:"Desk fan"},
 {id:"component-controller",kind:"component",name:"ESP32 DevKit",metadata:{family:"microcontroller_board",parameters:{logic_voltage_v:3.3,component_definition_id:"esp32-devkit-v1",gpio_map:{"signal-1":4,"signal-2":16}}}},
 {id:"component-temperature-sensor",kind:"component",name:"DS18B20",metadata:{family:"temperature_sensor",parameters:{component_definition_id:"ds18b20-module"}}},
 {id:"component-driver",kind:"component",name:"MOSFET",metadata:{family:"mosfet_driver",parameters:{}}},
 {id:"component-fan",kind:"component",name:"Desk fan",metadata:{family:"fan",parameters:{component_definition_id:"dc-fan-5v"}}},
 conn("component-temperature-sensor","signal","component-controller","signal-1","signal"),
 conn("component-controller","vcc-out","component-temperature-sensor","power","regulated-power"),
 conn("component-controller","ground","component-temperature-sensor","ground","ground"),
 conn("component-controller","signal-2","component-driver","signal","control"),
 conn("component-driver","load-output","component-fan","power","switched-power")],relationships:[]};

test("inspector shows real pins, derived pin check and connections",async({page})=>{
 await mock(page);await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:pinGraph}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/component-temperature-sensor/}).click();
 const rows=page.getByTestId("connection-rows");
 await expect(rows).toContainText("GPIO 4");await expect(rows).toContainText("3.3 V");await expect(rows).toContainText("GND");
 await expect(page.getByTestId("component-checks")).toContainText("Pin assigned");
 await expect(page.getByTestId("part-info")).toContainText("DS18B20");
 await page.getByRole("button",{name:"Show connections"}).click();
 await page.getByRole("button",{name:/Desk fan component-fan/}).click();
 await expect(page.getByTestId("connection-rows")).not.toContainText("GPIO");
});

test("simulation preview card shares state with the Simulation space",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 const preview=page.getByTestId("sim-preview");await expect(preview).toBeVisible();
 await preview.getByRole("slider").fill("27");await expect(preview).toContainText("Fan on");
 await page.getByRole("button",{name:"Simulation",exact:true}).click();
 await expect(page.getByTestId("sim-temperature")).toHaveValue("27");await expect(page.getByTestId("sim-fan-state")).toHaveText("ON");
});

test("simulation preview is absent for unsupported designs",async({page})=>{
 await mock(page,{supported:false,reasons:["No fan"],revisionId:"r",lastCompile:null,lastCompileCurrent:false});await page.goto("/?projectId=project-fan");
 await expect(page.getByTestId("part-info").or(page.getByTestId("pipeline-panel"))).toBeVisible();
 await expect(page.getByTestId("sim-preview")).toHaveCount(0);
});

test("code space shows numbered sketch, pins, libraries and board",async({page})=>{
 await mock(page,{...supported,source:"#include <OneWire.h>\n#define ONE_WIRE_PIN 4\n#define FAN_PIN 16",libraries:["OneWire@2.3.8","DallasTemperature@4.0.5"]});
 await page.goto("/?projectId=project-fan");await page.getByRole("button",{name:"Code",exact:true}).click();
 const code=page.getByTestId("code-source");
 await expect(code).toContainText("#define FAN_PIN 16");
 await expect(page.getByTestId("code-gutter")).toContainText("3");
 await expect(page.getByTestId("code-view")).toContainText("DS18B20 data");
 await expect(page.getByTestId("code-view")).toContainText("GPIO16");
 await expect(page.getByTestId("code-view")).toContainText("DallasTemperature@4.0.5");
 await expect(page.getByTestId("code-view")).toContainText("esp32:esp32:esp32");
});

test("code space explains unsupported designs",async({page})=>{
 await mock(page,{supported:false,reasons:["Firmware generation supports only an ESP32 DevKit V1 controller"],revisionId:"r",lastCompile:null,lastCompileCurrent:false});
 await page.goto("/?projectId=project-fan");await page.getByRole("button",{name:"Code",exact:true}).click();
 await expect(page.getByTestId("code-view")).toContainText("ESP32 DevKit V1");
 await expect(page.getByTestId("code-source")).toHaveCount(0);
});

test("rail and inspector use thumbnails rendered from the 3D models",async({page})=>{
 await mock(page);await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:pinGraph}));await page.goto("/?projectId=project-fan");
 const rows=page.locator(".rail-part-main img");
 await expect(rows.first()).toHaveAttribute("src",/^data:image\/png/);
 expect(await rows.count()).toBeGreaterThanOrEqual(3);
 await page.getByRole("button",{name:/Desk fan component-fan/}).click();
 await expect(page.locator(".component-card header img")).toHaveAttribute("src",/^data:image\/png/);
});

test("thumbnail failure falls back to icons and keeps the 3D scene",async({page})=>{
 await page.addInitScript(()=>{(window as any).__auraDisableThumbnails=true});
 await mock(page);await page.goto("/?projectId=project-fan");
 await expect(page.locator(".rail-icon").first()).toBeVisible();
 await expect(page.locator(".rail-part-main img")).toHaveCount(0);
 await page.waitForTimeout(700);
 expect((await page.evaluate(()=>(window as any).__auraSceneMetrics())).triangles).toBeGreaterThan(0);
});

test("simulation starts below the design's own thresholds and resets per revision",async({page})=>{
 await mock(page,{...supported,tOnC:20,tOffC:18,revisionId:"revision-low"});await page.goto("/?projectId=project-fan");
 await expect(page.getByTestId("sim-preview")).toContainText("Fan off");
 await expect(page.getByTestId("sim-preview")).toContainText("17.0 °C");
});

test("settings menu closes with Escape and returns focus",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 const trigger=page.getByRole("button",{name:"Settings"});await trigger.click();
 await expect(page.getByRole("menuitem",{name:"New design"})).toBeFocused();
 await page.keyboard.press("Escape");
 await expect(page.getByRole("menu")).toHaveCount(0);await expect(trigger).toBeFocused();
 await trigger.click();await page.mouse.click(800,600);await expect(page.getByRole("menu")).toHaveCount(0);
});

test("stage shows the concept status badge and an assembly selector",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 await expect(page.getByTestId("concept-badge")).toHaveText("Concept model");
 const assembly=page.getByLabel("Assembly");await expect(assembly).toHaveValue("all");
 await assembly.selectOption({label:"actuator"});await expect(assembly).toHaveValue("actuator");
});

test("pin picker proposes and commits a GPIO change through the shared revision path",async({page})=>{
 await mock(page);
 const wired={...graph,entities:graph.entities.map((e:any)=>e.id==="component-controller"?{...e,metadata:{family:"microcontroller_board",parameters:{gpio_map:{"signal-1":4,"signal-2":16}}}}:e.id==="component-driver"?{...e,metadata:{family:"mosfet_driver",parameters:{}}}:e)
  .concat([{id:"connection-gate",kind:"connection",metadata:{source_id:"component-controller",source_interface:"signal-2",target_id:"component-driver",target_interface:"signal",connection_type:"control"}}])};
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:wired}));
 const proposals:any[]=[];let committed=false;
 await page.route("**/api/projects/project-fan/pin-proposals",r=>{proposals.push(r.request().postDataJSON());r.fulfill({json:{proposalId:"proposal-pin",summary:"Move ESP32 signal-2 from GPIO16 to GPIO17"}})});
 await page.route("**/api/projects/project-fan/modification-proposals/proposal-pin/commit",r=>{committed=true;r.fulfill({json:{revision:2}})});
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/Logic-level MOSFET switch component-driver/}).click();
 const picker=page.getByLabel("Change pin for Gate (IN)");
 await expect(picker).toHaveValue("16");
 await expect(picker.locator("option[value='5']")).toHaveCount(0);
 await picker.selectOption("17");
 await expect.poll(()=>committed).toBe(true);
 expect(proposals).toEqual([{baseRevision:1,controllerId:"component-controller",port:"signal-2",gpio:17}]);
});

test("pin picker shows the verification rejection and changes nothing",async({page})=>{
 await mock(page);
 const wired={...graph,entities:graph.entities.map((e:any)=>e.id==="component-controller"?{...e,metadata:{family:"microcontroller_board",parameters:{gpio_map:{"signal-1":4,"signal-2":16}}}}:e)
  .concat([{id:"connection-gate",kind:"connection",metadata:{source_id:"component-controller",source_interface:"signal-2",target_id:"component-driver",target_interface:"signal",connection_type:"control"}}])};
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:wired}));
 await page.route("**/api/projects/project-fan/pin-proposals",r=>r.fulfill({json:{proposalId:"proposal-pin"}}));
 await page.route("**/api/projects/project-fan/modification-proposals/proposal-pin/commit",r=>r.fulfill({status:422,json:{detail:{code:"verification_rejected",reasons:["ESP32 DevKit has unsafe or conflicting GPIO assignments: signal-1=GPIO4, signal-2=GPIO4."]}}}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/Logic-level MOSFET switch component-driver/}).click();
 await page.getByLabel("Change pin for Gate (IN)").selectOption("4");
 await expect(page.getByTestId("pin-error")).toContainText("conflicting GPIO assignments");
});

test("code view shows a firmware load error with retry instead of hanging",async({page})=>{
 await mock(page);let calls=0;
 await page.route("**/api/projects/project-fan/firmware",r=>{calls++;calls===1?r.fulfill({status:500,json:{detail:"boom"}}):r.fulfill({json:supported})});
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Code",exact:true}).click();
 await expect(page.getByTestId("firmware-error")).toBeVisible();
 await page.getByRole("button",{name:"Retry"}).click();
 await expect(page.getByTestId("code-source")).toBeVisible();
});

test("fanControl block is editable, saved for the revision and flagged after a revision change",async({page})=>{
 const block="bool fanControl(bool prevOn, float tC, bool valid, float tOn, float tOff) {\n  return tC >= tOn;\n}\n";
 let edit:any=null;const saved:any[]=[];
 await mock(page);
 await page.route("**/api/projects/project-fan/firmware",r=>r.fulfill({json:{...supported,controlBlock:block,edit}}));
 await page.route("**/api/projects/project-fan/firmware/edit",r=>{if(r.request().method()==="PUT"){saved.push(r.request().postDataJSON());edit={revisionId:"revision-1",needsReview:false};r.fulfill({json:{saved:true}})}else{edit=null;r.fulfill({status:204,body:""})}});
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Code",exact:true}).click();
 const editor=page.getByLabel("Edit fanControl");
 await expect(editor).toHaveValue(block);
 await editor.fill(block.replace("return tC >= tOn;","return tC > tOn;"));
 await page.getByRole("button",{name:"Save edit"}).click();
 expect(saved).toEqual([{block:block.replace("return tC >= tOn;","return tC > tOn;"),revisionId:"revision-1"}]);
 await expect(page.getByTestId("edit-badge")).toHaveText("Edited fanControl");
 edit={revisionId:"revision-0",needsReview:true};
 await page.getByRole("button",{name:"Reset to generated"}).click();
 await expect(page.getByTestId("edit-badge")).toHaveCount(0);
});

test("wire rows show exact header pins, both endpoints, and selection highlights wired parts",async({page})=>{
 await mock(page);await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:pinGraph}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/component-temperature-sensor/}).click();
 const rows=page.getByTestId("connection-rows");
 await expect(rows).toContainText("IO4, J3 pin 13");await expect(rows).toContainText("(−)");
 await rows.getByRole("button",{name:/Data \(DQ\)/}).click();
 await expect(page.getByTestId("wire-endpoints")).toHaveText("DS18B20 · signal↔ESP32 DevKit · signal-1 (GPIO4 (IO4, J3 pin 13))");
 await expect(page.locator('.rail-part[data-highlighted="true"]')).toHaveCount(1);
 await expect(page.locator('.rail-part[data-highlighted="true"]')).toContainText("ESP32 DevKit");
 await expect(page.getByTestId("three-host")).toHaveAttribute("data-highlighted","component-controller");
});

test("a part without a detailed model is labelled a generic proxy",async({page})=>{
 const pump={...parts[3],semanticId:"component-pump",label:"Water pump",family:"small_dc_pump",assembledTransform:{position:[400,0,20]}};
 await mock(page);
 await page.route("**/api/projects/project-fan/assembly",r=>r.fulfill({json:{parts:[...parts,pump],connectors:[],relationships:[]}}));
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:{...graph,entities:[...graph.entities,{id:"component-pump",kind:"component",name:"Water pump",parent_id:"subsystem-actuator",metadata:{family:"small_dc_pump"}}]}}));
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:/Water pump component-pump/}).click();
 await expect(page.getByTestId("proxy-label")).toHaveText("Generic proxy — no detailed 3D model for this part yet");
 await page.getByRole("button",{name:/component-temperature-sensor/}).click();
 await expect(page.getByTestId("proxy-label")).toHaveCount(0);
});

test("cables run pin to pin, stay on their pins when exploded, and share numbers with the part card",async({page})=>{
 await mock(page);await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:pinGraph}));
 await page.goto("/?projectId=project-fan");
 await expect.poll(()=>page.evaluate(()=>(window as any).__auraWires?.().length??0)).toBeGreaterThan(0);
 const wires=async()=>page.evaluate(()=>(window as any).__auraWires());
 let list=await wires();
 expect(list.map((w:any)=>`${w.from}>${w.to}`)).toContain("component-temperature-sensor.DAT>component-controller.IO4");
 expect(list.map((w:any)=>`${w.from}>${w.to}`)).toContain("component-controller.IO16>component-driver.IN");
 for(const w of list){expect(w.startError,w.label).toBeLessThan(.5);expect(w.endError,w.label).toBeLessThan(.5)}
 await expect(page.getByTestId("wire-note")).toContainText("Illustrative routing — not a measured cable layout");
 await page.getByRole("button",{name:"View controls"}).click();await page.getByRole("button",{name:"Explode",exact:true}).click();
 list=await wires();for(const w of list){expect(w.startError).toBeLessThan(.5);expect(w.endError).toBeLessThan(.5)}
 const dat=list.find((w:any)=>w.from==="component-temperature-sensor.DAT");
 expect(dat.label).toBe(`${dat.number} · DS18B20 · DAT ↔ ESP32 DevKit · IO4 (GPIO4, J3 pin 13)`);
 await page.getByRole("button",{name:/component-temperature-sensor/}).click();
 await expect(page.getByTestId("connection-rows").getByTestId(`wire-number-${dat.number}`)).toBeVisible();
});

test("the 3D view picks a render quality and still draws the assembly",async({page})=>{
 await mock(page);await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:pinGraph}));
 await page.goto("/?projectId=project-fan");
 await expect.poll(()=>page.evaluate(()=>(window as any).__auraRenderQuality)).toMatch(/^(high|basic)$/);
 await expect.poll(()=>page.evaluate(()=>(window as any).__auraWires?.().length??0)).toBeGreaterThan(0);
 const shot=await page.locator(".three canvas").screenshot();
 expect(new Set(shot.subarray(100,shot.length).filter((_,i)=>i%97===0)).size).toBeGreaterThan(20);
});

test("guessed legacy tubes stay hidden and approximate routes are labelled",async({page})=>{
 await mock(page);
 const pump={id:"component-pump",kind:"component",name:"Water pump",metadata:{family:"small_dc_pump",parameters:{}}};
 const extra={id:"conn-pump",kind:"connection",name:"pump",metadata:{source_id:"component-driver",target_id:"component-pump",source_interface:"load-output",target_interface:"power",connection_type:"switched-power"}};
 const pumpPart={...parts[3],semanticId:"component-pump",label:"Water pump",family:"small_dc_pump",assembledTransform:{position:[400,0,20]}};
 await page.route("**/api/projects/project-fan/assembly",r=>r.fulfill({json:{parts:[...parts,pumpPart],connectors:[],relationships:[]}}));
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:{...pinGraph,entities:[...pinGraph.entities,pump,extra]}}));
 await page.goto("/?projectId=project-fan");
 await expect.poll(()=>page.evaluate(()=>(window as any).__auraWires?.().length??0)).toBeGreaterThan(0);
 expect(await page.evaluate(()=>(window as any).__auraLegacyWiresVisible())).toBe(false);
 expect(await page.evaluate(()=>(window as any).__auraApproximateLabels())).toBe(1);
 await page.getByLabel("Assembly").selectOption({index:1});
 expect(await page.evaluate(()=>(window as any).__auraLegacyWiresVisible())).toBe(false);
 await page.getByLabel("Assembly").selectOption("all");
});
