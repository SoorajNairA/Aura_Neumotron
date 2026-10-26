import * as THREE from "three";
import {describe,expect,it} from "vitest";
import {buildStudioModel} from "./studioModels";

const part=(semanticId:string,family:string,dimensions:number[],visualKind?:string)=>({semanticId,label:semanticId,family,visualKind,subsystem:"s",parentAssembly:"a",representationSource:"x",dimensions,assembledTransform:{position:[0,0,0]},explodedTransform:{position:[0,0,0]},verificationState:"conceptual"});
const size=(object:THREE.Object3D)=>new THREE.Box3().setFromObject(object).getSize(new THREE.Vector3());

describe("studio models",()=>{
 const cases:[string,string,number[],string?][]=[
  ["component-controller","microcontroller_board",[28,52,12],"esp32_devkit"],
  ["component-temperature-sensor","temperature_sensor",[22,16,6]],
  ["component-driver","mosfet_driver",[34,26,14]],
  ["component-fan","fan",[90,30,90]],
  ["component-power","low_voltage_power_source",[48,30,18]],
  ["component-pull-up","resistor",[7,3,3]],
  ["component-flyback-diode","flyback_diode",[10,3,3]],
 ];
 for(const [id,family,dims,kind] of cases)it(`builds a detailed ${family} near its planned footprint`,()=>{
  const group=buildStudioModel(part(id,family,dims,kind));
  expect(group).not.toBeNull();
  let meshes=0;group!.traverse(o=>{if((o as THREE.Mesh).isMesh)meshes++});
  expect(meshes).toBeGreaterThanOrEqual(family==="resistor"||family==="flyback_diode"?3:9);
  const box=size(group!);
  // Footprint (the two largest axes) stays within 25% of the planned dimensions so assembly layout is preserved.
  const planned=[...dims].sort((a,b)=>b-a),built=[box.x,box.y,box.z].sort((a,b)=>b-a);
  for(const index of [0,1])expect(Math.abs(built[index]-planned[index])/planned[index]).toBeLessThan(.25);
 });
 it("gives the fan a named rotor with nine blades",()=>{
  const rotor=buildStudioModel(part("component-fan","fan",[90,30,90]))!.getObjectByName("fan-rotor")!;
  expect(rotor).toBeDefined();
  expect(rotor.children.filter(child=>child.name==="fan-blade")).toHaveLength(9);
 });
 it("does not share materials between parts, so selection highlights stay per part",()=>{
  const first=buildStudioModel(part("a","fan",[90,30,90]))!,second=buildStudioModel(part("b","fan",[90,30,90]))!;
  const materials=(object:THREE.Object3D)=>{const found=new Set<THREE.Material>();object.traverse(o=>{const m=(o as THREE.Mesh).material;if(m)found.add(m as THREE.Material)});return found};
  const shared=[...materials(first)].filter(material=>materials(second).has(material));
  expect(shared).toHaveLength(0);
 });
 it("leaves other families to the existing proxies",()=>{
  expect(buildStudioModel(part("component-servo","servo",[23,12,29]))).toBeNull();
  expect(buildStudioModel(part("component-controller","microcontroller_board",[45,18,8],"arduino_nano"))).toBeNull();
 });
});
