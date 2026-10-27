export type ComponentGroup="Controller"|"Sensors"|"Actuators"|"Power"|"Other";
export const GROUP_ORDER:ComponentGroup[]=["Controller","Sensors","Actuators","Power","Other"];
export type PinRef={controllerId:string;port:string;gpio:number};
export type ConnectionRow={port:string;label:string;value:string;tone:"data"|"supply"|"ground"|"control";pin?:PinRef};
// ESP32 output-capable GPIOs minus strapping pins (0, 2, 5, 12, 15); the backend applies the same rule.
export const PICKABLE_GPIOS=[4,13,14,16,17,18,19,21,22,23,25,26,27,32,33];
export type CheckRow={id:string;title:string;detail:string;tone:"pass"|"warn"|"fail"};

const ACTUATORS=new Set(["fan","servo","small_dc_motor","small_dc_pump","mosfet_driver","motor_driver","relay_module","bare_relay"]);
const CONTROLLERS=new Set(["microcontroller_board","controller"]);

export function componentGroup(family:string|undefined):ComponentGroup{
 if(!family)return "Other";
 if(CONTROLLERS.has(family))return "Controller";
 if(family.endsWith("_sensor"))return "Sensors";
 if(ACTUATORS.has(family))return "Actuators";
 if(family==="low_voltage_power_source")return "Power";
 return "Other";
}

type Entity={id:string;kind:string;name?:string;metadata?:any};
const family=(entity:Entity|undefined)=>entity?.metadata?.family as string|undefined;
const params=(entity:Entity|undefined)=>(entity?.metadata?.parameters||{}) as Record<string,any>;

// Part numbers for curated catalogue ids; anything else shows its humanized family.
const PART_NUMBERS:Record<string,string>={"ds18b20-module":"DS18B20","esp32-devkit-v1":"ESP32-DevKitC","logic-mosfet-module":"Logic-level MOSFET module","dc-fan-5v":"5 V DC fan","1n4007-diode":"1N4007","resistor-4k7":"4.7 kΩ resistor","resistor-10k":"10 kΩ resistor","sg90-servo":"SG90","drv8833-module":"DRV8833","bme280-i2c-module":"BME280","arduino-nano-v3":"Arduino Nano","arduino-uno-r4":"Arduino UNO R4"};
const humanize=(value:string)=>value.replace(/[_-]+/g," ").replace(/^./,c=>c.toUpperCase());
export function partNumber(entity:Entity|undefined):string{
 if(!entity)return "";
 const id=params(entity).component_definition_id as string|undefined;
 return (id&&PART_NUMBERS[id])||humanize(family(entity)||"");
}

export function connectionRows(componentId:string,graph:{entities:Entity[]}|undefined):ConnectionRow[]{
 const entities=graph?.entities||[];const byId=new Map(entities.map(entity=>[entity.id,entity]));
 if(!byId.has(componentId))return [];
 const rows:ConnectionRow[]=[];const seen=new Set<string>();
 const add=(row:ConnectionRow)=>{if(!seen.has(row.port)){seen.add(row.port);rows.push(row)}};
 const self=byId.get(componentId)!;
 // Edges without a specific label still appear, so wired passives and supplies never read as unconnected.
 const generic=new Map<string,{others:string[];tone:ConnectionRow["tone"]}>();
 for(const edge of entities.filter(entity=>entity.kind==="connection").map(entity=>entity.metadata||{})){
  const mine=edge.source_id===componentId?"source":edge.target_id===componentId?"target":null;if(!mine)continue;
  const port:string=mine==="source"?edge.source_interface:edge.target_interface;
  const other=byId.get(mine==="source"?edge.target_id:edge.source_id);const otherPort:string=mine==="source"?edge.target_interface:edge.source_interface;
  const type:string=edge.connection_type;
  if(type==="ground"){add({port,label:"Ground (GND)",value:"GND",tone:"ground"});continue}
  if((type==="signal"||type==="control")&&CONTROLLERS.has(family(other)||"")){
   const gpio=params(other).gpio_map?.[otherPort];
   const sensor=family(self)?.endsWith("_sensor");
   const label=params(self).component_definition_id==="ds18b20-module"?"Data (DQ)":sensor?"Signal":"Gate (IN)";
   add({port,label,value:gpio!==undefined?`GPIO ${gpio}`:otherPort,tone:sensor?"data":"control",...(gpio!==undefined?{pin:{controllerId:other!.id,port:otherPort,gpio}}:{})});continue}
  if(type==="regulated-power"&&CONTROLLERS.has(family(other)||"")&&port==="power"){
   const volts=params(other).logic_voltage_v;add({port,label:"Supply (VDD)",value:volts?`${volts} V`:"Controller rail",tone:"supply"});continue}
  if(type==="switched-power"&&mine==="target"&&port==="power"){add({port,label:"Supply (+)",value:`Switched by ${family(other)==="mosfet_driver"?"MOSFET":humanize(family(other)||"driver")}`,tone:"supply"});continue}
  if(type==="power"&&mine==="target"&&port==="power"){const volts=params(other).voltage_v;add({port,label:"Supply (VCC)",value:volts?`${volts} V`:"Supply",tone:"supply"});continue}
  const entry=generic.get(port)||{others:[],tone:(type.includes("power")?"supply":type==="control"?"control":"data") as ConnectionRow["tone"]};
  entry.others.push(`${other?.name||humanize(family(other)||"part")} · ${otherPort}`);generic.set(port,entry);
 }
 for(const [port,{others,tone}] of generic)add({port,label:humanize(port),value:others.length>1?`${others.length} connections`:others[0],tone});
 const order={data:0,control:0,supply:1,ground:2};
 return rows.sort((a,b)=>order[a.tone]-order[b.tone]);
}

const PASS=new Set(["passed","source_verified","tool_verified","cross_checked"]);
// The realistic studio models apply only to the curated ESP32 fan workflow; every other design keeps proxies.
export function markStudioParts<T extends {parts:any[]}>(assembly:T,graph:{entities:Entity[]}|undefined):T{
 const ids=new Set((graph?.entities||[]).map(entity=>params(entity).component_definition_id));
 const studio=ids.has("dc-fan-5v")&&ids.has("ds18b20-module")&&ids.has("esp32-devkit-v1");
 return {...assembly,parts:assembly.parts.map(part=>({...part,studio}))};
}

export function checksForComponent(componentId:string,findings:any[]|undefined):CheckRow[]{
 const order={fail:0,warn:1,pass:2};
 return (findings||[]).filter(finding=>[...(finding.semanticIds||[]),...(finding.entity_ids||[])].includes(componentId))
  .map(finding=>({id:String(finding.findingId||finding.id),title:String(finding.summary||finding.message||finding.check),detail:humanize(String(finding.check||"")),
   tone:(finding.status==="failed"?"fail":PASS.has(finding.status)?"pass":"warn") as CheckRow["tone"]}))
  .sort((a,b)=>order[a.tone]-order[b.tone]);
}

export function modelBadge(project:any,activeLabel?:string):string{
 if(!project)return "";
 if(project.planningMode==="deterministic_fallback")return "Offline fallback";
 if(project.planningMode==="deterministic_test")return "Deterministic";
 const origin=project.assessment?.planningOrigin||{};const provider=origin.provider?humanize(String(origin.provider)):"Live model";
 const model=String(origin.model||"");
 if(!model&&activeLabel)return activeLabel;
 return /nemotron/i.test(model)?`Nemotron · ${provider}`:`${model||"Model"} · ${provider}`;
}

// One-line descriptions for curated parts, limited to facts held in the catalogue evidence.
const DESCRIPTIONS:Record<string,string>={"ds18b20-module":"Digital temperature sensor, ±0.5 °C from −10 to +85 °C (datasheet). 1-Wire interface.","esp32-devkit-v1":"ESP32 development board with 3.3 V logic GPIO.","logic-mosfet-module":"Logic-level N-MOSFET switch for the fan supply.","dc-fan-5v":"5 V DC fan. Current draw is a curated estimate.","resistor-4k7":"Pull-up on the 1-Wire data line.","1n4007-diode":"Flyback diode across the inductive load."};
export function partDescription(entity:any):string{
 const id=entity?.metadata?.parameters?.component_definition_id as string|undefined;
 return (id&&DESCRIPTIONS[id])||"";
}
export const GROUP_ROLE:Record<ComponentGroup,string>={Controller:"Controller",Sensors:"Sensor",Actuators:"Actuator",Power:"Power",Other:"Component"};
export function neighbours(componentId:string,graph:{entities:any[]}|undefined):string[]{
 return [...new Set((graph?.entities||[]).filter(entity=>entity.kind==="connection").flatMap(entity=>{const m=entity.metadata||{};return m.source_id===componentId?[m.target_id]:m.target_id===componentId?[m.source_id]:[]}))];
}
