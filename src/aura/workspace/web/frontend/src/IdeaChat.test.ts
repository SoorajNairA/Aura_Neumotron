import {describe,expect,it} from "vitest";
import {canPropose,costLine,ruleSentence,slotBadge} from "./ideaHelpers";

const req=(fn:any,power:any)=>({function:fn,power,budget:{value:"",source:"assumption",status:"open"}});

describe("idea chat helpers",()=>{
 it("labels where a requirement came from",()=>{
  expect(slotBadge("user")).toBe("You said");expect(slotBadge("default")).toBe("Default");expect(slotBadge("assumption")).toBe("Assumed");
 });
 it("mirrors the backend readiness rule",()=>{
  const scope={status:"IN_SCOPE"};
  expect(canPropose({requirements:req({value:"x",status:"agreed"},{value:"USB",status:"proposed"}),scope})).toBe(true);
  expect(canPropose({requirements:req({value:"x",status:"proposed"},{value:"USB",status:"agreed"}),scope})).toBe(false);
  expect(canPropose({requirements:req({value:"x",status:"agreed"},{value:"",status:"open"}),scope})).toBe(false);
  expect(canPropose({requirements:req({value:"x",status:"agreed"},{value:"USB",status:"agreed"}),scope:{status:"OUT_OF_SCOPE"}})).toBe(false);
  expect(canPropose(undefined)).toBe(false);
 });
 it("states the cost as an estimate and counts unpriced parts",()=>{
  expect(costLine({totalUsd:15.02,estimate:true,excluded:["dc-fan-5v"]})).toBe("Estimate: $15.02 · 1 part unpriced");
  expect(costLine({totalUsd:0,estimate:true,excluded:[]})).toBe("Estimate: $0.00");
  expect(costLine({totalUsd:1,estimate:true,excluded:["a","b"]})).toBe("Estimate: $1.00 · 2 parts unpriced");
 });
});

describe("rule sentences",()=>{
 const ios=[{id:"soil_1",value:"percent",unit:"%"},{id:"pump_1",value:"bool",unit:""},{id:"temp_1",value:"celsius",unit:"°C"},{id:"servo_1",value:"angle",unit:"°"},{id:"button_1",value:"bool",unit:""}] as any;
 it("states the rule in plain words",()=>{
  expect(ruleSentence({input:"soil_1",when:"below",threshold:30,release:45,output:"pump_1",onValue:true,offValue:false,minOnSeconds:5},ios))
   .toBe("When soil moisture is below 30 %, turn pump on (off again above 45 %, at least 5 s)");
  expect(ruleSentence({input:"temp_1",when:"above",threshold:26,release:null,output:"servo_1",onValue:90,offValue:0,minOnSeconds:null},ios))
   .toBe("When temperature is above 26 °C, set servo to 90° (back to 0° otherwise)");
  expect(ruleSentence({input:"button_1",when:"on",threshold:null,release:null,output:"pump_1",onValue:true,offValue:false,minOnSeconds:null},ios))
   .toBe("When button is on, turn pump on (off again when it is off)");
 });
});
