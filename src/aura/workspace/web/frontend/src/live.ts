import {fanControl} from "./fanControl";
import type {SerialLine} from "./hardware";
import {evaluate,Io,Rule,Value} from "./rules";

export const LIVE_LABEL="Live board — values reported by the firmware over USB serial";
const MISMATCH_LINES=3;

export function telemetryInputs(telemetry:Record<string,any>,ios:Io[]):Record<string,Value|null>{
 const inputs:Record<string,Value|null>={};
 for(const io of ios)if(io.supported&&io.role==="input"&&io.id in telemetry){const raw=telemetry[io.id];inputs[io.id]=raw===null?null:io.value==="bool"?Number(raw)>0:Number(raw)}
 return inputs;
}
export function telemetryOutputs(telemetry:Record<string,any>,ios:Io[]):Record<string,Value>{
 const outputs:Record<string,Value>={};
 for(const io of ios)if(io.supported&&io.role==="output"&&io.id in telemetry)outputs[io.id]=io.value==="bool"?Number(telemetry[io.id])>0:Number(telemetry[io.id]);
 return outputs;
}
export type LiveStep={t:number;inputs:Record<string,Value|null>;outputs:Record<string,Value>};
export const history=(lines:SerialLine[],ios:Io[]):LiveStep[]=>lines.filter(line=>line.telemetry)
 .map(line=>({t:Date.parse(line.time)||0,inputs:telemetryInputs(line.telemetry!,ios),outputs:telemetryOutputs(line.telemetry!,ios)}));

// One-step check: from the board's previous reported outputs, would the approved rules produce what it reports now?
// An output is flagged only when the last three predictions all differ, so one noisy line is not a finding.
export function agreement(steps:LiveStep[],rules:Rule[],ios:Io[]):{disagree:string[]}{
 const outputs=ios.filter(io=>io.supported&&io.role==="output").map(io=>io.id),since:Record<string,number>={},misses:Record<string,number>={};
 const onValue=(id:string)=>rules.find(rule=>rule.output===id)?.onValue;
 steps.forEach((step,index)=>{
  if(index>0){
   const previous=steps[index-1].outputs;
   const result=evaluate(rules,step.inputs,{outputs:{...previous},since:{...since}},step.t);
   for(const id of outputs)if(id in step.outputs&&id in previous&&rules.some(rule=>rule.output===id))
    misses[id]=Number(result.outputs[id])===Number(step.outputs[id])?0:(misses[id]||0)+1;
  }
  for(const id of outputs){const on=onValue(id);if(on!==undefined&&Number(step.outputs[id])===Number(on)&&(index===0||Number(steps[index-1].outputs[id])!==Number(on)))since[id]=step.t}
 });
 return {disagree:outputs.filter(id=>(misses[id]||0)>=MISMATCH_LINES)};
}

export function fanAgreement(lines:SerialLine[],tOn:number,tOff:number):boolean{
 const steps=lines.filter(line=>line.telemetry&&"fan" in line.telemetry);let misses=0;
 for(let index=1;index<steps.length;index++){
  const previous=Number(steps[index-1].telemetry!.fan)>0,t=steps[index].telemetry!.t_c;
  const expected=fanControl(previous,t===null||t===undefined?null:Number(t),tOn,tOff).on;
  misses=expected===Number(steps[index].telemetry!.fan)>0?0:misses+1;
 }
 return misses<MISMATCH_LINES;
}
