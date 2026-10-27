import {describe,expect,it} from "vitest";
import {agreement,fanAgreement,history,telemetryInputs,telemetryOutputs} from "./live";

const ios=[{id:"soil_1",role:"input",value:"percent",supported:true},{id:"button_1",role:"input",value:"bool",supported:true},
 {id:"pump_1",role:"output",value:"bool",supported:true},{id:"servo_1",role:"output",value:"angle",supported:true},{id:"bme_1",role:null,value:null,supported:false}] as any;
const rule={input:"soil_1",when:"below" as const,threshold:30,release:45,output:"pump_1",onValue:true,offValue:false,minOnSeconds:null};
const line=(seq:number,soil:number|null,pump:number)=>({seq,time:new Date(Date.UTC(2026,9,28,14,0,seq)).toISOString(),text:"",telemetry:{rev:"r",soil_1:soil,pump_1:pump}});

describe("live telemetry",()=>{
 it("maps telemetry to inputs and outputs",()=>{
  const t={rev:"r",soil_1:20.5,button_1:1,pump_1:1,servo_1:90};
  expect(telemetryInputs(t,ios)).toEqual({soil_1:20.5,button_1:true});
  expect(telemetryInputs({rev:"r",soil_1:null,button_1:0},ios)).toEqual({soil_1:null,button_1:false});
  expect(telemetryOutputs(t,ios)).toEqual({pump_1:true,servo_1:90});
 });
 it("agrees when the board follows the rule, including the hysteresis hold",()=>{
  const lines=[line(1,50,0),line(2,25,1),line(3,40,1),line(4,46,0),line(5,null,0)];
  expect(agreement(history(lines,ios),[rule],ios).disagree).toEqual([]);
 });
 it("flags an output only after three consecutive differing lines",()=>{
  const two=[line(1,50,0),line(2,20,0),line(3,20,0),line(4,50,0)];
  expect(agreement(history(two,ios),[rule],ios).disagree).toEqual([]);
  const three=[line(1,50,0),line(2,20,0),line(3,20,0),line(4,20,0)];
  expect(agreement(history(three,ios),[rule],ios).disagree).toEqual(["pump_1"]);
 });
 it("respects minOnSeconds from when the board switched on",()=>{
  const timed={...rule,minOnSeconds:10};
  const lines=[line(1,20,1),line(2,50,1),line(3,50,1),line(4,50,1)];
  expect(agreement(history(lines,ios),[timed],ios).disagree).toEqual([]);
 });
 it("checks fan firmware against fanControl",()=>{
  const fan=(seq:number,t:number|null,on:number)=>({seq,time:"",text:"",telemetry:{rev:"r",t_c:t,fan:on}});
  expect(fanAgreement([fan(1,20,0),fan(2,27,1),fan(3,25,1),fan(4,null,1)],26,24)).toBe(true);
  expect(fanAgreement([fan(1,20,0),fan(2,27,0),fan(3,28,0),fan(4,29,0)],26,24)).toBe(false);
 });
});
