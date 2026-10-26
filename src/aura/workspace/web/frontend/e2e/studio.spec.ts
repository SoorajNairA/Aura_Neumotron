import {expect,test,Page} from "@playwright/test";

const LABEL="Behavioral simulation — control logic only. Not electrical verification, not firmware execution.";
const rows:[string,string,string][]=[["component-controller","ESP32 DevKit","electronics"],["component-temperature-sensor","DS18B20 temperature sensor","sensor"],["component-driver","Logic-level MOSFET switch","electronics"],["component-fan","Desk fan","actuator"]];
const parts=rows.map(([semanticId,label,subsystem],i)=>({semanticId,label,family:semanticId==="component-fan"?"fan":undefined,subsystem,parentAssembly:"desk-fan",representationSource:"conceptual procedural model",dimensions:[60,30,60],assembledTransform:{position:[i*80,0,20]},explodedTransform:{position:[i*90,0,40]},verificationState:"estimated"}));
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
