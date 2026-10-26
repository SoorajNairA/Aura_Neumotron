export type FanReason="above_on"|"below_off"|"in_band"|"sensor_fault";

// Mirrors fanControl() in the generated firmware: unknown temperature runs the fan (fail-safe).
export function fanControl(prevOn:boolean,tempC:number|null,tOn:number,tOff:number):{on:boolean;reason:FanReason}{
 if(tempC===null)return {on:true,reason:"sensor_fault"};
 if(tempC>=tOn)return {on:true,reason:"above_on"};
 if(tempC<=tOff)return {on:false,reason:"below_off"};
 return {on:prevOn,reason:"in_band"};
}
