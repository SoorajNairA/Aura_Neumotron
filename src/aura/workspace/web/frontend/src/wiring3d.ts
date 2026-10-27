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
  wires.push({number,connectionId:entity.id,role,color:WIRE_COLORS[role],from,to,label:`${number} · ${from.name} · ${from.pin}${from.detail} ↔ ${to.name} · ${to.pin}${to.detail}`});
 }
 return wires;
}
// Connections with an end that has no modelled pin: drawn dashed as an approximate route, never as a real wire.
resolveWires.unresolved=(graph:{entities:Entity[]}|undefined)=>graph?ends(graph).filter(item=>!item.fromPin||!item.toPin)
 .map(item=>({connectionId:item.entity.id,from:item.m.source_id,to:item.m.target_id,role:ROLE[item.m.connection_type]})):[];

// A jumper: straight up from each pin, then a smooth arc over the parts whose height grows with distance.
export function jumperCurve(a:THREE.Vector3,b:THREE.Vector3):THREE.CatmullRomCurve3{
 const rise=5,arc=THREE.MathUtils.clamp(a.distanceTo(b)*.22,8,32),top=Math.max(a.z,b.z)+arc;
 const lift=(p:THREE.Vector3)=>new THREE.Vector3(p.x,p.y,p.z+rise);
 const mid=new THREE.Vector3((a.x+b.x)/2,(a.y+b.y)/2,top);
 return new THREE.CatmullRomCurve3([a.clone(),lift(a),mid,lift(b),b.clone()],false,"centripetal");
}
