import {describe,expect,it} from "vitest";
import {PICKABLE_GPIOS,checksForComponent,componentGroup,connectionRows,modelBadge,partNumber} from "./studio";

const conn=(source_id:string,source_interface:string,target_id:string,target_interface:string,connection_type:string)=>({id:`connection-${source_id}-${target_id}-${connection_type}`,kind:"connection",metadata:{source_id,target_id,source_interface,target_interface,connection_type}});
const comp=(id:string,family:string,parameters:Record<string,unknown>={})=>({id,kind:"component",name:id,metadata:{family,parameters}});
// Mirrors the planner's real fan graph shape (GET /api/projects/{id}/graph).
const graph={entities:[
 comp("component-controller","microcontroller_board",{logic_voltage_v:3.3,component_definition_id:"esp32-devkit-v1",gpio_map:{"signal-1":4,"signal-2":16}}),
 comp("component-temperature-sensor","temperature_sensor",{component_definition_id:"ds18b20-module"}),
 comp("component-driver","mosfet_driver",{component_definition_id:"logic-mosfet-module"}),
 comp("component-fan","fan",{voltage_v:5}),
 comp("component-power","low_voltage_power_source",{voltage_v:5}),
 comp("component-pull-up","resistor",{resistance_ohm:4700}),
 conn("component-temperature-sensor","signal","component-controller","signal-1","signal"),
 conn("component-controller","signal-2","component-driver","signal","control"),
 conn("component-controller","vcc-out","component-temperature-sensor","power","regulated-power"),
 conn("component-power","ground","component-temperature-sensor","ground","ground"),
 conn("component-driver","load-output","component-fan","power","switched-power"),
 conn("component-power","ground","component-fan","ground","ground"),
]};

describe("studio helpers",()=>{
 it("groups families like the concept",()=>{
  expect(componentGroup("microcontroller_board")).toBe("Controller");
  expect(componentGroup("temperature_sensor")).toBe("Sensors");
  expect(componentGroup("mosfet_driver")).toBe("Actuators");
  expect(componentGroup("fan")).toBe("Actuators");
  expect(componentGroup("low_voltage_power_source")).toBe("Power");
  expect(componentGroup("resistor")).toBe("Other");
  expect(componentGroup(undefined)).toBe("Other");
 });
 it("derives DS18B20 pin rows from the graph",()=>{
  expect(connectionRows("component-temperature-sensor",graph)).toMatchObject([
   {port:"signal",label:"Data (DQ)",value:"GPIO 4",tone:"data",pin:{controllerId:"component-controller",port:"signal-1",gpio:4},header:"IO4, J3 pin 13",polarity:"signal"},
   {port:"power",label:"Supply (VDD)",value:"3.3 V",tone:"supply",polarity:"+"},
   {port:"ground",label:"Ground (GND)",value:"GND",tone:"ground"}]);
 });
 it("never invents a GPIO for parts not wired to the controller",()=>{
  const rows=connectionRows("component-fan",graph);
  expect(rows.some(row=>row.value.startsWith("GPIO"))).toBe(false);
  expect(rows.map(row=>row.value)).toEqual(["Switched by MOSFET","GND"]);
  expect(connectionRows("missing",graph)).toEqual([]);
  expect(connectionRows("component-driver",graph)[0]).toMatchObject({port:"signal",label:"Gate (IN)",value:"GPIO 16",tone:"control",pin:{controllerId:"component-controller",port:"signal-2",gpio:16}});
 });
 it("offers only output-capable, non-strapping pins for reassignment",()=>{
  expect(PICKABLE_GPIOS).toContain(16);expect(PICKABLE_GPIOS).toContain(17);
  for(const pin of [0,2,5,6,12,15,34,35,36,39])expect(PICKABLE_GPIOS).not.toContain(pin);
 });
 it("maps findings to check tones for one component",()=>{
  const findings=[{findingId:"a",summary:"Datasheet range",check:"catalogue-properties",status:"source_verified",semanticIds:["component-temperature-sensor"]},
   {findingId:"b",summary:"Wiring is conceptual",check:"assembly",status:"conceptual",entity_ids:["component-temperature-sensor"]},
   {findingId:"c",summary:"Broken",check:"x",status:"failed",semanticIds:["component-temperature-sensor"]},
   {findingId:"d",summary:"Other part",check:"x",status:"failed",semanticIds:["component-fan"]}];
  expect(checksForComponent("component-temperature-sensor",findings).map(row=>[row.id,row.tone])).toEqual([["c","fail"],["b","warn"],["a","pass"]]);
 });
 it("labels part numbers and the planning model honestly",()=>{
  expect(partNumber(graph.entities[1])).toBe("DS18B20");
  expect(partNumber(comp("x","small_dc_motor"))).toBe("Small dc motor");
  expect(partNumber(undefined)).toBe("");
  expect(modelBadge({planningMode:"live_model",assessment:{planningOrigin:{provider:"nebius",model:"nvidia/nemotron-3-super-120b-a12b"}}})).toBe("Nemotron · Nebius");
  expect(modelBadge({planningMode:"live_model",assessment:{planningOrigin:{provider:"vertex",model:"gemini-3.1-flash-lite"}}})).toBe("gemini-3.1-flash-lite · Vertex");
  expect(modelBadge({planningMode:"deterministic_fallback"})).toBe("Offline fallback");
  expect(modelBadge({planningMode:"deterministic_test"})).toBe("Deterministic");
  expect(modelBadge(undefined)).toBe("");
 });
});

import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {markStudioParts} from "./studio";

describe("review fixes",()=>{
 it("lists real connections for passives and the supply instead of claiming none",()=>{
  const g={entities:[...graph.entities,
   comp("component-flyback-diode","flyback_diode"),
   conn("component-temperature-sensor","signal","component-pull-up","terminal-a","signal"),
   conn("component-pull-up","terminal-b","component-controller","vcc-out","regulated-power"),
   conn("component-driver","load-output","component-flyback-diode","cathode","switched-power"),
   conn("component-flyback-diode","anode","component-power","ground","ground"),
   conn("component-power","power","component-driver","power","power")]};
  expect(connectionRows("component-pull-up",g).map(row=>row.port)).toEqual(["terminal-a","terminal-b"]);
  expect(connectionRows("component-flyback-diode",g).map(row=>row.port)).toContain("cathode");
  expect(connectionRows("component-power",g).map(row=>row.port)).toContain("power");
 });
 it("marks studio parts only for the curated ESP32 fan workflow",()=>{
  const assembly={parts:[{semanticId:"component-fan",family:"fan"},{semanticId:"component-power",family:"low_voltage_power_source"}]};
  const fanGraph={entities:[...graph.entities,comp("component-fan","fan",{component_definition_id:"dc-fan-5v"})]};
  expect(markStudioParts(assembly as any,fanGraph).parts.every((part:any)=>part.studio)).toBe(true);
  const solar={entities:[comp("component-controller","microcontroller_board",{component_definition_id:"esp32-devkit-v1"}),comp("component-power","low_voltage_power_source")]};
  expect(markStudioParts(assembly as any,solar).parts.some((part:any)=>part.studio)).toBe(false);
 });
 it("keeps text colours at 4.5:1 or better on white",()=>{
  const css=readFileSync(resolve(__dirname,"styles.css"),"utf8");
  const tokens=Object.fromEntries([...css.matchAll(/--([a-z-]+):(#[0-9a-f]{6})/gi)].map(m=>[m[1],m[2]]));
  const lum=(hex:string)=>{const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.03928?v/12.92:((v+.055)/1.055)**2.4);return .2126*c[0]+.7152*c[1]+.0722*c[2]};
  const ratio=(a:string,b:string)=>{const [x,y]=[lum(a),lum(b)].sort((p,q)=>q-p);return (x+.05)/(y+.05)};
  for(const token of ["text","text-soft","text-dim","accent","warn-text","pass-text","fail"])expect(ratio(tokens[token],"#ffffff"),token).toBeGreaterThanOrEqual(4.5);
 });
});
