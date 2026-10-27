import * as THREE from "three";
import {describe,expect,it} from "vitest";
import {jumperCurve,resolveWires,WIRE_COLORS} from "./wiring3d";

const comp=(id:string,name:string,family:string,parameters:any={})=>({id,kind:"component",name,metadata:{family,parameters}});
const conn=(id:string,s:string,si:string,t:string,ti:string,type:string)=>({id,kind:"connection",name:id,metadata:{source_id:s,source_interface:si,target_id:t,target_interface:ti,connection_type:type}});
const fan=(gpio={"signal-1":4,"signal-2":16})=>({entities:[
 comp("c","ESP32 DevKit","microcontroller_board",{gpio_map:gpio,component_definition_id:"esp32-devkit-v1"}),comp("t","DS18B20","temperature_sensor"),
 comp("d","MOSFET","mosfet_driver"),comp("f","Desk fan","fan"),comp("p","5V supply","low_voltage_power_source"),comp("k","Pump","small_dc_pump"),
 conn("w1","t","signal","c","signal-1","signal"),conn("w2","c","vcc-out","t","power","regulated-power"),conn("w3","p","ground","t","ground","ground"),
 conn("w4","c","signal-2","d","signal","control"),conn("w5","d","load-output","f","power","switched-power"),conn("w6","p","power","d","power","power"),
 conn("w7","d","load-output","k","power","switched-power"),conn("w8","p","mount","c","body-mount","mechanical")]});

describe("pin-to-pin wires",()=>{
 it("maps every electrical connection to two real pins with role, colour and a stable number",()=>{
  const wires=resolveWires(fan());
  expect(wires.map(w=>[w.number,`${w.from.part}.${w.from.pin}`,`${w.to.part}.${w.to.pin}`,w.role])).toEqual([
   [1,"t.DAT","c.IO4","signal"],[2,"c.3V3","t.VCC","power"],[3,"p.-","t.GND","ground"],[4,"c.IO16","d.IN","control"],[5,"d.OUT+","f.+","switched"],[6,"p.+","d.V+","power"]]);
  expect(wires[0].color).toBe(WIRE_COLORS.signal);expect(wires[2].color).toBe(WIRE_COLORS.ground);
  expect(wires[0].label).toBe("1 · DS18B20 · DAT ↔ ESP32 DevKit · IO4 (GPIO4, J3 pin 13)");
 });
 it("follows a GPIO change to the new header pin",()=>{
  expect(resolveWires(fan({"signal-1":17,"signal-2":16}))[0].to.pin).toBe("IO17");
 });
 it("never invents a wire for a part without pins; it reports it as approximate",()=>{
  const graph=fan();
  expect(resolveWires(graph).some(w=>w.to.part==="k")).toBe(false);
  expect(resolveWires.unresolved(graph).map(u=>u.connectionId)).toEqual(["w7"]);
 });
 it("draws a jumper that leaves and lands exactly on the pins and arcs above them",()=>{
  const a=new THREE.Vector3(0,0,10),b=new THREE.Vector3(60,20,4),curve=jumperCurve(a,b);
  expect(curve.getPoint(0).distanceTo(a)).toBeLessThan(1e-6);expect(curve.getPoint(1).distanceTo(b)).toBeLessThan(1e-6);
  expect(Math.max(...curve.getPoints(40).map(p=>p.z))).toBeGreaterThan(10+10);
 });
});

describe("wire label review",()=>{
 it("only controller pins carry DevKitC header positions",()=>{
  const graph={entities:[comp("c","ESP32 DevKit","microcontroller_board",{gpio_map:{}}),comp("t","DS18B20","temperature_sensor"),conn("w","c","ground","t","ground","ground")]};
  expect(resolveWires(graph)[0].label).toBe("1 · ESP32 DevKit · GND (J2 pin 14) ↔ DS18B20 · GND");
 });
 it("keeps short jumpers low",()=>{
  const curve=jumperCurve(new THREE.Vector3(0,0,0),new THREE.Vector3(150,0,0));
  expect(Math.max(...curve.getPoints(40).map(p=>p.z))).toBeLessThan(40);
 });
});
