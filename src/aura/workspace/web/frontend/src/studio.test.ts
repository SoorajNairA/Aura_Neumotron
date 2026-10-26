import {describe,expect,it} from "vitest";
import {checksForComponent,componentGroup,connectionRows,modelBadge,partNumber} from "./studio";

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
  expect(connectionRows("component-temperature-sensor",graph)).toEqual([
   {port:"signal",label:"Data (DQ)",value:"GPIO 4",tone:"data"},
   {port:"power",label:"Supply (VDD)",value:"3.3 V",tone:"supply"},
   {port:"ground",label:"Ground (GND)",value:"GND",tone:"ground"}]);
 });
 it("never invents a GPIO for parts not wired to the controller",()=>{
  const rows=connectionRows("component-fan",graph);
  expect(rows.some(row=>row.value.startsWith("GPIO"))).toBe(false);
  expect(rows.map(row=>row.value)).toEqual(["Switched by MOSFET","GND"]);
  expect(connectionRows("missing",graph)).toEqual([]);
  expect(connectionRows("component-driver",graph)[0]).toEqual({port:"signal",label:"Gate (IN)",value:"GPIO 16",tone:"control"});
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
