export type BenchKind="ds18b20"|"fan";
export const BENCH_LABEL="Behavioral model — not hardware";
// DallasTemperature's DEVICE_DISCONNECTED_C; the generated firmware treats it as a sensor fault.
export const DS18B20_DISCONNECTED=-127;

export function benchKind(family:string|undefined,definitionId:string|undefined):BenchKind|null{
 if(family==="temperature_sensor"&&definitionId==="ds18b20-module")return "ds18b20";
 if(family==="fan")return "fan";
 return null;
}

// 12-bit resolution (0.0625 °C) inside the datasheet's -55..125 °C range.
export function ds18b20Reading(tempC:number,connected:boolean):number{
 if(!connected)return DS18B20_DISCONNECTED;
 return Math.round(Math.min(125,Math.max(-55,tempC))/0.0625)*0.0625;
}
