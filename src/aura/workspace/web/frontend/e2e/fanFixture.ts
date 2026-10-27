import {Page} from "@playwright/test";

export const LABEL="Behavioral simulation — control logic only. Not electrical verification, not firmware execution.";
export const rows:[string,string,string][]=[["component-controller","ESP32 DevKit","electronics"],["component-temperature-sensor","DS18B20 temperature sensor","sensor"],["component-driver","Logic-level MOSFET switch","electronics"],["component-fan","Desk fan","actuator"]];
export const parts=rows.map(([semanticId,label,subsystem],i)=>({semanticId,label,family:({"component-controller":"microcontroller_board","component-temperature-sensor":"temperature_sensor","component-driver":"mosfet_driver","component-fan":"fan"} as Record<string,string>)[semanticId],subsystem,parentAssembly:"desk-fan",representationSource:"conceptual procedural model",dimensions:[60,30,60],assembledTransform:{position:[i*80,0,20]},explodedTransform:{position:[i*90,0,40]},verificationState:"estimated"}));
export const project={projectId:"project-fan",objective:"Design a temperature-controlled desk fan",revision:1,status:"ready",planningMode:"live_model",assessment:{planningOrigin:{provider:"nebius",model:"nvidia/nemotron-3-super-120b-a12b",planningMode:"live_model"}},capability:{status:"SUPPORTED",reasons:[]},representations:[]};
export const graph={project_id:"project-fan",entities:[{id:"project-fan",kind:"project",name:"Desk fan"},...parts.map(p=>({id:p.semanticId,kind:"component",name:p.label,parent_id:`subsystem-${p.subsystem}`,metadata:{}}))],relationships:[]};
export const supported={supported:true,reasons:[],tOnC:26,tOffC:24,pins:{temperature_data:4,fan_gate:16},fqbn:"esp32:esp32:esp32",libraries:["OneWire@2.3.8"],source:"// sketch",revisionId:"revision-1",lastCompile:null,lastCompileCurrent:false};

export async function mock(page:Page,firmware:any=supported){
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
