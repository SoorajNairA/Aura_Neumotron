import {expect,test,Page} from "@playwright/test";

const LABEL="Behavioral simulation — control logic only. Not electrical verification, not firmware execution.";
const rows:[string,string,string][]=[["component-controller","ESP32 DevKit","electronics"],["component-temperature-sensor","DS18B20 temperature sensor","sensor"],["component-driver","Logic-level MOSFET switch","electronics"],["component-fan","Desk fan","actuator"]];
const parts=rows.map(([semanticId,label,subsystem],i)=>({semanticId,label,family:semanticId==="component-fan"?"fan":undefined,subsystem,parentAssembly:"desk-fan",representationSource:"conceptual procedural model",dimensions:[60,30,60],assembledTransform:{position:[i*80,0,20]},explodedTransform:{position:[i*90,0,40]},verificationState:"estimated"}));
const project={projectId:"project-fan",objective:"Design a temperature-controlled desk fan",revision:1,status:"ready",planningMode:"deterministic_test",capability:{status:"SUPPORTED",reasons:[]},representations:[]};
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
const spinning=(page:Page)=>page.evaluate(()=>(window as any).__auraFanSpinning());

test("simulation tab drives the fan with hysteresis and an honest label",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Simulation",exact:true}).click();
 await expect(page.getByTestId("sim-label")).toHaveText(LABEL);
 const slider=page.getByTestId("sim-temperature"),state=page.getByTestId("sim-fan-state");
 await slider.fill("26");await expect(state).toHaveText("ON");expect(await spinning(page)).toBe(true);
 await slider.fill("25");await expect(state).toHaveText("ON");
 await slider.fill("24");await expect(state).toHaveText("OFF");expect(await spinning(page)).toBe(false);
 await page.getByTestId("sim-fault").check();await expect(state).toHaveText("ON");
 await expect(page.getByTestId("sim-log")).toContainText("sensor fault");
 await expect(page.getByTestId("simulation-panel")).toContainText("GPIO4");
});

test("simulation tab is disabled with the reason for unsupported designs",async({page})=>{
 await mock(page,{supported:false,reasons:["Firmware generation supports only an ESP32 DevKit V1 controller"],revisionId:"revision-1",lastCompile:null,lastCompileCurrent:false});
 await page.goto("/?projectId=project-fan");
 const tab=page.getByRole("button",{name:"Simulation",exact:true});
 await expect(tab).toBeDisabled();
 await expect(tab).toHaveAttribute("title",/ESP32 DevKit V1/);
});

test("simulation uses the design's own thresholds",async({page})=>{
 await mock(page,{...supported,tOnC:30,tOffC:28});await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Simulation",exact:true}).click();
 const slider=page.getByTestId("sim-temperature"),state=page.getByTestId("sim-fan-state");
 await slider.fill("29");await expect(state).toHaveText("OFF");
 await slider.fill("30");await expect(state).toHaveText("ON");
});

test("slider range follows thresholds outside 10-40 °C",async({page})=>{
 await mock(page,{...supported,tOnC:45,tOffC:43});await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Simulation",exact:true}).click();
 await page.getByTestId("sim-temperature").fill("46");
 await expect(page.getByTestId("sim-fan-state")).toHaveText("ON");
});

test("firmware can be compiled from the Code space with honest status",async({page})=>{
 await mock(page,{...supported,source:"#define FAN_PIN 16",lastCompile:{status:"passed",revisionId:"revision-0",sizeBytes:1,errors:[],missing:null},lastCompileCurrent:false});
 await page.route("**/api/projects/project-fan/firmware/compile",r=>r.fulfill({json:{status:"toolchain_missing",missing:"arduino-cli",errors:[],sizeBytes:null,revisionId:"revision-1"}}));
 await page.goto("/?projectId=project-fan");await page.getByRole("button",{name:"Code",exact:true}).click();
 const status=page.getByTestId("fw-status");
 await expect(status).toContainText("not the current design revision");
 await page.getByRole("button",{name:"COMPILE"}).click();
 await expect(status).toContainText("Toolchain missing: arduino-cli");
 
 await expect(page.getByTestId("code-source")).toContainText("#define FAN_PIN 16");
});

const ios=[{id:"soil_1",component_id:"component-temperature-sensor",name:"Soil sensor",definition_id:"capacitive-soil-v1",role:"input",value:"percent",unit:"%",low:0,high:100,gpio:32,supported:true},
 {id:"pump_1",component_id:"component-driver",name:"Pump switch",definition_id:"logic-mosfet-module",role:"output",value:"bool",unit:"",low:0,high:1,gpio:16,supported:true}];
const generic={supported:true,reasons:[],kind:"generic",pins:{soil_1:32,pump_1:16},ios,rules:[{input:"soil_1",when:"below",threshold:30,release:45,output:"pump_1",onValue:true,offValue:false,minOnSeconds:null}],
 rulesSource:"default",explanation:"Default rule — not generated by the live model",droppedRules:[],fqbn:"esp32:esp32:esp32",libraries:[],source:"// sketch",revisionId:"revision-1",lastCompile:null,lastCompileCurrent:false};

test("generic simulation follows the rule list and injects faults",async({page})=>{
 await mock(page,generic);await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"Simulation",exact:true}).click();
 await expect(page.getByTestId("sim-label")).toHaveText("Behavioral model — same rule as firmware, not running on hardware");
 const pump=page.getByTestId("sim-output-pump_1");
 await expect(pump).toHaveText("pump_1 OFF");
 await page.getByTestId("sim-input-soil_1").fill("20");await expect(pump).toHaveText("pump_1 ON");
 await page.getByTestId("sim-fault-pump_1").selectOption("stalled");await expect(page.getByTestId("sim-warnings")).toHaveText("Pump switch commanded on but not moving");
 await page.getByTestId("sim-fault-pump_1").selectOption("");
 await page.getByTestId("sim-fault-soil_1").selectOption("disconnected");await expect(pump).toHaveText("pump_1 OFF");
 await expect(page.getByTestId("sim-warnings")).toHaveCount(0);
 await page.getByTestId("sim-fault-pump_1").selectOption("shorted");await expect(pump).toHaveText("pump_1 ON");
 await expect(page.getByTestId("sim-warnings")).toHaveText("Pump switch driver shorted: output stuck on");
});

test("generic Code view shows rule source, dropped rules, parts without a driver and compile failure",async({page})=>{
 const bme={id:"environmental_sensor_1",component_id:"component-bme",name:"BME280",definition_id:"bme280-breakout",role:null,value:null,unit:"",low:0,high:0,gpio:17,supported:false};
 const dropped={input:"temp_1",when:"above",threshold:26,release:24,output:"led_1",onValue:true,offValue:false,minOnSeconds:null};
 await mock(page,{...generic,ios:[...ios,bme],droppedRules:[dropped],addedWithoutDriver:[{semanticId:"component-driver",name:"Pump switch",port:"signal-2",gpio:16}]});
 await page.route("**/api/projects/project-fan/firmware/compile",r=>r.fulfill({json:{status:"failed",missing:null,errors:[{message:"'x' was not declared",line:3}],sizeBytes:null,revisionId:"revision-1"}}));
 await page.goto("/?projectId=project-fan");await page.getByRole("button",{name:"Code",exact:true}).click();
 await expect(page.getByTestId("rules-source")).toHaveText("Default rule — not generated by the live model");
 await expect(page.getByTestId("code-rules")).toContainText("When soil moisture is below 30 %, turn pump on (off again above 45 %)");
 await expect(page.getByTestId("dropped-rules")).toContainText("When temperature is above 26, turn led on");
 await expect(page.getByTestId("no-driver")).toContainText("BME280 · GPIO17 — No driver yet");
 await expect(page.getByTestId("added-without-driver")).toHaveCount(0);
 await page.getByRole("button",{name:"COMPILE"}).click();
 await expect(page.getByTestId("fw-status")).toContainText("Firmware does not compile: 'x' was not declared (line 3)");
});
