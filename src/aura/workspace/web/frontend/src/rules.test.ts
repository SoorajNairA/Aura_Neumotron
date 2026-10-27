import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {describe,expect,it} from "vitest";
import {applyFaults,evaluate,initialState,Rule} from "./rules";

// Same truth table the generated C++ control() is compiled and run against.
const table:{name:string;rules:Rule[];steps:{t:number;inputs:Record<string,number|boolean|null>;expect:Record<string,number|boolean>}[]}[]=
 JSON.parse(readFileSync(resolve(__dirname,"../../../../../../tests/fixtures/rule_truth_table.json"),"utf8"));

describe("rule evaluator",()=>{
 for(const testCase of table)it(`matches the firmware truth table: ${testCase.name}`,()=>{
  let state=initialState(testCase.rules);
  for(const step of testCase.steps){
   const result=evaluate(testCase.rules,step.inputs,state,step.t*1000);state=result.state;
   for(const [id,value] of Object.entries(step.expect))expect(Number(result.outputs[id]),`${testCase.name} t=${step.t} ${id}`).toBe(Number(value));
  }
 });
});

describe("fault injection",()=>{
 const names={soil_1:"Soil sensor",pump_1:"Pump"};
 it("disconnects and sticks inputs",()=>{
  expect(applyFaults({soil_1:20},{},[{kind:"disconnected",io:"soil_1"}]).inputs.soil_1).toBeNull();
  expect(applyFaults({soil_1:20},{},[{kind:"stuck",io:"soil_1",value:70}]).inputs.soil_1).toBe(70);
 });
 it("reports a stalled actuator that is commanded on",()=>{
  const result=applyFaults({},{pump_1:true},[{kind:"stalled",io:"pump_1"}],names);
  expect(result.outputs.pump_1).toBe(true);expect(result.moving.pump_1).toBe(false);
  expect(result.warnings).toEqual(["Pump commanded on but not moving"]);
  expect(applyFaults({},{pump_1:false},[{kind:"stalled",io:"pump_1"}],names).warnings).toEqual([]);
 });
 it("forces a shorted driver on",()=>{
  const result=applyFaults({},{pump_1:false},[{kind:"shorted",io:"pump_1"}],names);
  expect(result.outputs.pump_1).toBe(true);expect(result.moving.pump_1).toBe(true);
  expect(result.warnings).toEqual(["Pump driver shorted: output stuck on"]);
 });
});
