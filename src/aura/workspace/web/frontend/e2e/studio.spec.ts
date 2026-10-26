import {expect,test,Page} from "@playwright/test";

const LABEL="Behavioral simulation — control logic only. Not electrical verification, not firmware execution.";
const rows:[string,string,string][]=[["component-controller","ESP32 DevKit","electronics"],["component-temperature-sensor","DS18B20 temperature sensor","sensor"],["component-driver","Logic-level MOSFET switch","electronics"],["component-fan","Desk fan","actuator"]];
const parts=rows.map(([semanticId,label,subsystem],i)=>({semanticId,label,family:({"component-controller":"microcontroller_board","component-temperature-sensor":"temperature_sensor","component-driver":"mosfet_driver","component-fan":"fan"} as Record<string,string>)[semanticId],subsystem,parentAssembly:"desk-fan",representationSource:"conceptual procedural model",dimensions:[60,30,60],assembledTransform:{position:[i*80,0,20]},explodedTransform:{position:[i*90,0,40]},verificationState:"estimated"}));
const project={projectId:"project-fan",objective:"Design a temperature-controlled desk fan",revision:1,status:"ready",planningMode:"live_model",assessment:{planningOrigin:{provider:"nebius",model:"nvidia/nemotron-3-super-120b-a12b",planningMode:"live_model"}},capability:{status:"SUPPORTED",reasons:[]},representations:[]};
const graph={project_id:"project-fan",entities:[{id:"project-fan",kind:"project",name:"Desk fan"},...parts.map(p=>({id:p.semanticId,kind:"component",name:p.label,parent_id:`subsystem-${p.subsystem}`,metadata:{}}))],relationships:[]};
const supported={supported:true,reasons:[],tOnC:26,tOffC:24,pins:{temperature_data:4,fan_gate:16},fqbn:"esp32:esp32:esp32",libraries:["OneWire@2.3.8"],source:"// sketch",revisionId:"revision-1",lastCompile:null,lastCompileCurrent:false};

async function mock(page:Page,firmware:any=supported){
 await page.route("**/api/projects",r=>r.fulfill({json:[project]}));
 await page.route("**/api/projects/project-fan",r=>r.fulfill({json:project}));
 await page.route("**/api/projects/project-fan/revisions",r=>r.fulfill({json:[{revision:1,summary:"Project created"}]}));
 await page.route("**/api/projects/project-fan/assembly",r=>r.fulfill({json:{parts,connectors:[],relationships:[]}}));
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:graph}));
 await page.route("**/api/projects/project-fan/verification",r=>r.fulfill({json:{state:"pass",summary:{},findings:[]}}));
 await page.route("**/api/projects/project-fan/work",r=>r.fulfill({json:{items:[]}}));
 await page.route("**/api/projects/project-fan/narrations",r=>r.fulfill({json:[]}));
 await page.route("**/api/projects/project-fan/firmware",r=>r.fulfill({json:firmware}));
}

test("studio top bar shows spaces, honest disabled features and the planning model",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 for(const name of ["Design","Code","Simulation"])await expect(page.getByRole("button",{name,exact:true})).toBeEnabled();
 const build=page.getByRole("button",{name:"Build",exact:true});
 await expect(build).toBeDisabled();await expect(build).toHaveAttribute("title","Coming next: USB upload, live telemetry");
 const connect=page.getByRole("button",{name:"Connect device"});
 await expect(connect).toBeDisabled();await expect(connect).toHaveAttribute("title","Coming next: USB serial upload and telemetry");
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
 {id:"component-fan",kind:"component",name:"Desk fan",metadata:{family:"fan",parameters:{}}},
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
