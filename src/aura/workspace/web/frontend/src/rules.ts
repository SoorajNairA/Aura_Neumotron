// Same rule semantics as the generated firmware's control() (src/aura/firmware/generic.py); both pass tests/fixtures/rule_truth_table.json.
export type Rule={input:string;when:"above"|"below"|"on"|"off";threshold:number|null;release:number|null;output:string;
 onValue:boolean|number;offValue:boolean|number;minOnSeconds:number|null};
export type Io={id:string;component_id:string;name:string;definition_id:string|null;role:"input"|"output"|null;
 value:"celsius"|"percent"|"bool"|"angle"|null;unit:string;low:number;high:number;gpio:number|null;supported:boolean};
export type Value=number|boolean;
export type RuleState={outputs:Record<string,Value>;since:Record<string,number>};
export type Fault={kind:"disconnected"|"stuck"|"stalled"|"shorted";io:string;value?:number};

export function initialState(rules:Rule[]):RuleState{
 const outputs:Record<string,Value>={};
 for(const rule of rules)if(!(rule.output in outputs))outputs[rule.output]=rule.offValue;
 return {outputs,since:{}};
}

export function evaluate(rules:Rule[],inputs:Record<string,Value|null>,state:RuleState,nowMs:number):{outputs:Record<string,Value>;state:RuleState}{
 const outputs={...state.outputs},since={...state.since};
 const set=(id:string,value:Value,on:Value,minOnMs:number)=>{
  const current=Number(outputs[id]);
  if(current===Number(value))return;
  if(current===Number(on)&&minOnMs&&nowMs-(since[id]??0)<minOnMs)return;  // minOnSeconds keeps the output on
  if(Number(value)===Number(on))since[id]=nowMs;
  outputs[id]=value;
 };
 for(const rule of rules){
  const raw=inputs[rule.input],minOnMs=Math.round((rule.minOnSeconds??0)*1000);
  // A cooling fan runs while its sensor is faulted; everything else goes to its off value.
  if(raw===null||raw===undefined){set(rule.output,rule.output.startsWith("fan_")?rule.onValue:rule.offValue,rule.onValue,0);continue}
  const v=Number(raw),t=rule.threshold??0;
  const [condition,release]=rule.when==="above"?[v>=t,rule.release!==null?v<=rule.release:v<t]
   :rule.when==="below"?[v<=t,rule.release!==null?v>=rule.release:v>t]
   :rule.when==="on"?[v>=.5,v<.5]:[v<.5,v>=.5];
  if(condition)set(rule.output,rule.onValue,rule.onValue,minOnMs);
  else if(release)set(rule.output,rule.offValue,rule.onValue,minOnMs);
 }
 return {outputs,state:{outputs,since}};
}

export function applyFaults(inputs:Record<string,Value|null>,outputs:Record<string,Value>,faults:Fault[],names:Record<string,string>={}){
 const nextInputs={...inputs},nextOutputs={...outputs},warnings:string[]=[];
 const moving:Record<string,boolean>=Object.fromEntries(Object.entries(outputs).map(([id,value])=>[id,Number(value)>0]));
 for(const fault of faults){
  const name=names[fault.io]||fault.io;
  if(fault.kind==="disconnected")nextInputs[fault.io]=null;
  else if(fault.kind==="stuck")nextInputs[fault.io]=fault.value??null;
  else if(fault.kind==="stalled"){moving[fault.io]=false;if(Number(nextOutputs[fault.io])>0)warnings.push(`${name} commanded on but not moving`)}
  else{nextOutputs[fault.io]=typeof nextOutputs[fault.io]==="number"?nextOutputs[fault.io]:true;moving[fault.io]=true;warnings.push(`${name} driver shorted: output stuck on`)}
 }
 return {inputs:nextInputs,outputs:nextOutputs,warnings,moving};
}
