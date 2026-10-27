import {describe,expect,it} from "vitest";
import {connectedParts,endpointLabel,ESP32_DEVKITC,pinLabel,POWER_PINS,polarity} from "./pinout";
import {connectionRows} from "./studio";

const graph={entities:[
 {id:"component-controller",kind:"component",name:"ESP32 DevKit",metadata:{family:"microcontroller_board",parameters:{gpio_map:{"signal-1":4,"signal-2":16}}}},
 {id:"component-temperature-sensor",kind:"component",name:"DS18B20",metadata:{family:"temperature_sensor",parameters:{component_definition_id:"ds18b20-module"}}},
 {id:"component-driver",kind:"component",name:"MOSFET",metadata:{family:"mosfet_driver"}},
 {id:"w1",kind:"connection",metadata:{source_id:"component-temperature-sensor",target_id:"component-controller",source_interface:"data",target_interface:"signal-1",connection_type:"signal"}},
 {id:"w2",kind:"connection",metadata:{source_id:"component-controller",target_id:"component-driver",source_interface:"signal-2",target_interface:"signal",connection_type:"control"}},
 {id:"w3",kind:"connection",metadata:{source_id:"component-controller",target_id:"component-temperature-sensor",source_interface:"ground",target_interface:"ground",connection_type:"ground"}}]};

describe("ESP32-DevKitC pin table",()=>{
 it("matches the Espressif header layout",()=>{
  expect(ESP32_DEVKITC[4]).toEqual({label:"IO4",header:"J3",position:13,side:"right"});
  expect(ESP32_DEVKITC[16]).toEqual({label:"IO16",header:"J3",position:12,side:"right"});
  expect(ESP32_DEVKITC[32]).toEqual({label:"IO32",header:"J2",position:7,side:"left"});
  expect(ESP32_DEVKITC[36].label).toBe("VP");
  expect(POWER_PINS["3V3"]).toEqual([{header:"J2",position:1,side:"left"}]);
  expect(POWER_PINS.GND.map(p=>`${p.header}-${p.position}`)).toEqual(["J2-14","J3-1","J3-7"]);
 });
 it("labels pins, endpoints and polarity",()=>{
  expect(pinLabel(4)).toBe("GPIO4 (IO4, J3 pin 13)");
  expect(pinLabel(99)).toBe("GPIO99 (not on DevKitC header)");
  expect(endpointLabel("DS18B20","data",4)).toBe("DS18B20 · data (GPIO4 (IO4, J3 pin 13))");
  expect(endpointLabel("Fan","power")).toBe("Fan · power");
  expect([polarity("power"),polarity("vcc-out"),polarity("ground"),polarity("data")]).toEqual(["+","+","−","signal"]);
 });
 it("finds parts wired to a selected part",()=>{
  expect(connectedParts("component-temperature-sensor",graph)).toEqual(["component-controller"]);
  expect(connectedParts("component-controller",graph).sort()).toEqual(["component-driver","component-temperature-sensor"]);
 });
 it("adds header pin, polarity and both endpoints to connection rows",()=>{
  const row=connectionRows("component-temperature-sensor",graph).find(r=>r.port==="data")!;
  expect(row.header).toBe("IO4, J3 pin 13");expect(row.polarity).toBe("signal");
  expect(row.endpoints).toEqual(["DS18B20 · data","ESP32 DevKit · signal-1 (GPIO4 (IO4, J3 pin 13))"]);
  expect(connectionRows("component-temperature-sensor",graph).find(r=>r.port==="ground")!.polarity).toBe("−");
 });
});
