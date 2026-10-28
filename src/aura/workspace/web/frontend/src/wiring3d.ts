import * as THREE from "three";
import {ESP32_DEVKITC,POWER_PINS} from "./pinout";

export type WireRole="power"|"ground"|"signal"|"control"|"switched";
export const WIRE_COLORS:Record<WireRole,number>={power:0xd23a2f,ground:0x1c1e20,signal:0xe8b923,control:0xe07a1f,switched:0x2f6fd0};
const ROLE:Record<string,WireRole>={power:"power","regulated-power":"power",ground:"ground",signal:"signal",control:"control","switched-power":"switched"};

// Graph interface name → printed pin name on each part's 3D model (studioModels.ts anchors).
export const INTERFACE_PINS:Record<string,Record<string,string>>={
 microcontroller_board:{"vcc-out":"3V3",ground:"GND",power:"5V"},
 temperature_sensor:{signal:"DAT",power:"VCC",ground:"GND"},
 mosfet_driver:{signal:"IN",power:"V+",ground:"V-","load-output":"OUT+"},
 relay_module:{signal:"IN",power:"VCC",ground:"GND","load-output":"NO"},
 fan:{power:"+",ground:"-"},low_voltage_power_source:{power:"+",ground:"-"},
 flyback_diode:{cathode:"K",anode:"A"},resistor:{"terminal-a":"A","terminal-b":"B"},
 soil_moisture_sensor:{signal:"AOUT",power:"VCC",ground:"GND"},light_sensor:{signal:"AO",power:"VCC",ground:"GND"},
 motion_sensor:{signal:"OUT",power:"VCC",ground:"GND"},indicator:{signal:"A",power:"A",ground:"K"},switch:{signal:"1",ground:"2"},
 servo:{signal:"SIG",power:"V+",ground:"GND"},breadboard:{power:"+",ground:"-"},
 environmental_sensor:{signal:"SDA",power:"VCC",ground:"GND"},distance_sensor:{signal:"SDA",power:"VCC",ground:"GND"},orientation_sensor:{signal:"SDA",power:"VCC",ground:"GND"},
};

type Entity={id:string;kind:string;name?:string;metadata?:any};
export type PinEnd={part:string;pin:string;name:string;detail:string;iface:string};
export type Wire={number:number;connectionId:string;role:WireRole;color:number;from:PinEnd;to:PinEnd;label:string};

const where=(pin:string)=>{const gpio=Object.entries(ESP32_DEVKITC).find(([,p])=>p.label===pin);if(gpio)return ` (GPIO${gpio[0]}, ${gpio[1].header} pin ${gpio[1].position})`;
 const power=POWER_PINS[pin as keyof typeof POWER_PINS]?.[0];return power?` (${power.header} pin ${power.position})`:""};

export function pinFor(entity:Entity|undefined,iface:string):string|null{
 if(!entity)return null;const family=entity.metadata?.family||"";
 if(family==="microcontroller_board"){
  const gpio=entity.metadata?.parameters?.gpio_map?.[iface];
  if(gpio!==undefined)return ESP32_DEVKITC[Number(gpio)]?.label??null;
 }
 return INTERFACE_PINS[family]?.[iface]??null;
}

function ends(graph:{entities:Entity[]}){
 const byId=new Map(graph.entities.map(entity=>[entity.id,entity]));
 return graph.entities.filter(entity=>entity.kind==="connection"&&ROLE[entity.metadata?.connection_type]).sort((a,b)=>a.id.localeCompare(b.id)).map(entity=>{
  const m=entity.metadata,source=byId.get(m.source_id),target=byId.get(m.target_id);
  return {entity,m,source,target,fromPin:pinFor(source,m.source_interface),toPin:pinFor(target,m.target_interface)};
 });
}

export function resolveWires(graph:{entities:Entity[]}|undefined):Wire[]{
 if(!graph)return [];
 const wires:Wire[]=[];
 for(const {entity,m,source,target,fromPin,toPin} of ends(graph)){
  if(!fromPin||!toPin)continue;
  const role=ROLE[m.connection_type],number=wires.length+1;
    // DevKitC header positions belong only to controller pins; a sensor's own GND is just GND.
  const detail=(entity:Entity|undefined,pin:string)=>entity?.metadata?.family==="microcontroller_board"?where(pin):"";
  const from={part:m.source_id,pin:fromPin,name:source?.name||m.source_id,detail:detail(source,fromPin),iface:m.source_interface},to={part:m.target_id,pin:toPin,name:target?.name||m.target_id,detail:detail(target,toPin),iface:m.target_interface};
  // The graph models the driver as a high-side switch; real low-side MOSFET modules switch the load's − side instead.
  const caution=m.source_interface==="load-output"&&source?.metadata?.family==="mosfet_driver"?" — check module polarity: low-side modules switch the load's − side":"";
  wires.push({number,connectionId:entity.id,role,color:WIRE_COLORS[role],from,to,label:`${number} · ${from.name} · ${from.pin}${from.detail} ↔ ${to.name} · ${to.pin}${to.detail}${caution}`});
 }
 return wires;
}
// Connections with an end that has no modelled pin: drawn dashed as an approximate route, never as a real wire.
resolveWires.unresolved=(graph:{entities:Entity[]}|undefined)=>graph?ends(graph).filter(item=>!item.fromPin||!item.toPin)
 .map(item=>({connectionId:item.entity.id,from:item.m.source_id,to:item.m.target_id,role:ROLE[item.m.connection_type]})):[];

// A tidy harness route: straight up from the pin to this wire's lane height, along X, then along Y, straight down
// onto the other pin. Corners are rounded so the tube reads as a real cable; every leg is axis-aligned.
export function harnessPath(a:THREE.Vector3,b:THREE.Vector3,height:number,radius=2):THREE.CurvePath<THREE.Vector3>{
 const raw=[a.clone(),new THREE.Vector3(a.x,a.y,height),new THREE.Vector3(b.x,a.y,height),new THREE.Vector3(b.x,b.y,height),b.clone()];
 const points=raw.filter((point,index)=>index===0||point.distanceTo(raw[index-1])>1e-6);
 const path=new THREE.CurvePath<THREE.Vector3>();let cursor=points[0];
 for(let i=1;i<points.length-1;i++){
  const corner=points[i],before=points[i-1],after=points[i+1];
  const r=Math.min(radius,corner.distanceTo(before)/2,corner.distanceTo(after)/2);
  const entry=corner.clone().add(before.clone().sub(corner).setLength(r)),exit=corner.clone().add(after.clone().sub(corner).setLength(r));
  if(cursor.distanceTo(entry)>1e-6)path.add(new THREE.LineCurve3(cursor,entry));
  path.add(new THREE.QuadraticBezierCurve3(entry,corner.clone(),exit));cursor=exit;
 }
 path.add(new THREE.LineCurve3(cursor,points[points.length-1]));
 return path;
}

// Lane index per wire: shortest horizontal run lowest, so long wires pass over short ones and no two share a height.
export function assignLanes(lengths:number[]):number[]{
 const order=lengths.map((length,index)=>({length,index})).sort((p,q)=>p.length-q.length||p.index-q.index);
 const lanes=new Array<number>(lengths.length);order.forEach((item,lane)=>{lanes[item.index]=lane});return lanes;
}
