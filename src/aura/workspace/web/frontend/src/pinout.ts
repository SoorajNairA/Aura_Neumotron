// ESP32-DevKitC V4 headers, from Espressif's "ESP32-DevKitC V4 Getting Started Guide", Header Block table
// (docs.espressif.com/projects/esp-idf/en/stable/esp32/hw-reference/esp32/get-started-devkitc.html).
// J2 is the left header and J3 the right one with the antenna at the top; pin 1 is next to the antenna.
type Side="left"|"right";
export type HeaderPin={header:"J2"|"J3";position:number;side:Side};
export const J2=["3V3","EN","VP","VN","IO34","IO35","IO32","IO33","IO25","IO26","IO27","IO14","IO12","GND","IO13","SD2","SD3","CMD","5V"];
export const J3=["GND","IO23","IO22","TX","RX","IO21","GND","IO19","IO18","IO5","IO17","IO16","IO4","IO0","IO2","IO15","SD1","SD0","CLK"];
const GPIO_OF:Record<string,number>={VP:36,VN:39,TX:1,RX:3,SD2:9,SD3:10,CMD:11,SD1:8,SD0:7,CLK:6};

export const ESP32_DEVKITC:Record<number,{label:string}&HeaderPin>={};
export const POWER_PINS:Record<"3V3"|"5V"|"GND"|"EN",HeaderPin[]>={"3V3":[],"5V":[],GND:[],EN:[]};
for(const [header,labels,side] of [["J2",J2,"left"],["J3",J3,"right"]] as const)labels.forEach((label,index)=>{
 const pin={header,position:index+1,side} as HeaderPin;
 if(label in POWER_PINS)POWER_PINS[label as keyof typeof POWER_PINS].push(pin);
 else ESP32_DEVKITC[GPIO_OF[label]??Number(label.slice(2))]={label,...pin};
});

export const headerLabel=(gpio:number)=>{const pin=ESP32_DEVKITC[gpio];return pin?`${pin.label}, ${pin.header} pin ${pin.position}`:null};
export const pinLabel=(gpio:number)=>`GPIO${gpio} (${headerLabel(gpio)??"not on DevKitC header"})`;
export const endpointLabel=(part:string,iface:string,gpio?:number)=>`${part} · ${iface}${gpio!==undefined?` (${pinLabel(gpio)})`:""}`;
export function polarity(iface:string):"+"|"−"|"signal"{
 const name=iface.toLowerCase();
 if(/ground|gnd/.test(name))return "−";
 return /power|vcc|vdd|3v3|5v|vin/.test(name)?"+":"signal";
}

const ELECTRICAL=new Set(["power","ground","control","signal","regulated-power","switched-power"]);
// Parts sharing an electrical wire with the selected part, for highlighting.
export function connectedParts(componentId:string,graph:{entities:any[]}|undefined):string[]{
 const ids=new Set<string>();
 for(const entity of graph?.entities||[]){
  const m=entity.metadata||{};if(entity.kind!=="connection"||!ELECTRICAL.has(m.connection_type))continue;
  if(m.source_id===componentId&&m.target_id)ids.add(m.target_id);
  if(m.target_id===componentId&&m.source_id)ids.add(m.source_id);
 }
 ids.delete(componentId);return [...ids];
}
