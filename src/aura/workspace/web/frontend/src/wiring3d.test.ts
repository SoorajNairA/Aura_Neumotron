import * as THREE from "three";
import {describe,expect,it} from "vitest";
import {assignLanes,harnessPath,resolveWires,WIRE_COLORS} from "./wiring3d";

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

});

describe("wire label review",()=>{
 it("only controller pins carry DevKitC header positions",()=>{
  const graph={entities:[comp("c","ESP32 DevKit","microcontroller_board",{gpio_map:{}}),comp("t","DS18B20","temperature_sensor"),conn("w","c","ground","t","ground","ground")]};
  expect(resolveWires(graph)[0].label).toBe("1 · ESP32 DevKit · GND (J2 pin 14) ↔ DS18B20 · GND");
 });

});

describe("review: switched-load polarity",()=>{
 it("marks driver-to-load wires as needing a module polarity check",()=>{
  const wire=resolveWires(fan()).find(w=>w.from.pin==="OUT+")!;
  expect(wire.label).toContain("check module polarity: low-side modules switch the load's − side");
 });
});

describe("clean harness routing",()=>{
 it("rises from a pin, runs flat at its lane height in straight X then Y legs, and drops onto the other pin",()=>{
  const a=new THREE.Vector3(0,0,5),b=new THREE.Vector3(60,30,2),h=20,path=harnessPath(a,b,h);
  expect(path.getPoint(0).distanceTo(a)).toBeLessThan(1e-6);expect(path.getPoint(1).distanceTo(b)).toBeLessThan(1e-6);
  for(const p of path.getSpacedPoints(400)){
   const onRiseA=Math.abs(p.x-a.x)<1e-3&&Math.abs(p.y-a.y)<1e-3,onDropB=Math.abs(p.x-b.x)<1e-3&&Math.abs(p.y-b.y)<1e-3;
   const flat=Math.abs(p.z-h)<1e-3,nearCorner=[[a.x,a.y],[b.x,a.y],[b.x,b.y]].some(([x,y])=>Math.hypot(p.x-x,p.y-y)<2.01)&&p.z>h-2.01;
   expect(onRiseA||onDropB||nearCorner||(flat&&(Math.abs(p.y-a.y)<1e-3||Math.abs(p.x-b.x)<1e-3)),`${p.toArray()}`).toBe(true);
  }
 });
 it("gives every wire its own lane, shortest lowest",()=>{expect(assignLanes([30,5,12])).toEqual([2,0,1])});
});
