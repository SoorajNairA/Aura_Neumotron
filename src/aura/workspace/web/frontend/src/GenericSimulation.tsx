import {useEffect,useMemo,useRef,useState} from "react";
import {applyFaults,evaluate,Fault,initialState,Io,Rule,RuleState,Value} from "./rules";

export const GENERIC_SIMULATION_LABEL="Behavioral model — same rule as firmware, not running on hardware";
const INPUT_FAULTS=["disconnected","stuck"] as const,OUTPUT_FAULTS=["stalled","shorted"] as const;
const FAULT_LABEL:Record<Fault["kind"],string>={disconnected:"Sensor disconnected",stuck:"Sensor stuck at value",stalled:"Actuator stalled",shorted:"Driver shorted"};

const startValue=(io:Io):Value=>io.value==="bool"?false:io.value==="celsius"?20:Math.round((io.low+io.high)/2);
export const outputText=(value:Value|undefined)=>typeof value==="number"?`${value}°`:value?"ON":"OFF";

export function GenericSimulation({ios,rules,revisionId,onMoving}:{ios:Io[];rules:Rule[];revisionId?:string|null;onMoving?:(moving:Record<string,boolean>)=>void}){
 const inputs=ios.filter(io=>io.supported&&io.role==="input"),outputs=ios.filter(io=>io.supported&&io.role==="output");
 const names=useMemo(()=>Object.fromEntries(ios.map(io=>[io.id,io.name])),[ios]);
 const [values,setValues]=useState<Record<string,Value>>(()=>Object.fromEntries(inputs.map(io=>[io.id,startValue(io)])));
 const [faults,setFaults]=useState<Record<string,Fault>>({});
 const [now,setNow]=useState(()=>Date.now());
 const state=useRef<RuleState>(initialState(rules));
 // Each revision starts fresh; the clock ticks so minOnSeconds plays out in real time.
 useEffect(()=>{state.current=initialState(rules);setFaults({});setValues(Object.fromEntries(inputs.map(io=>[io.id,startValue(io)])))},[revisionId]);
 useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),250);return()=>clearInterval(timer)},[]);
 const list=Object.values(faults);
 const sensed=applyFaults(values,{},list).inputs;
 const result=evaluate(rules,sensed,state.current,now);state.current=result.state;
 const shown=applyFaults(sensed,result.outputs,list,names);
 const movingKey=JSON.stringify(shown.moving);
 useEffect(()=>{onMoving?.(shown.moving)},[movingKey]);
 useEffect(()=>()=>onMoving?.({}),[]);
 const setFault=(io:Io,kind:string)=>setFaults(current=>{const next={...current};delete next[io.id];
  if(kind)next[io.id]={kind:kind as Fault["kind"],io:io.id,value:kind==="stuck"?Number(values[io.id]):undefined};return next});
 const faultSelect=(io:Io,kinds:readonly Fault["kind"][])=><select aria-label={`Fault for ${io.id}`} data-testid={`sim-fault-${io.id}`} value={faults[io.id]?.kind||""} onChange={event=>setFault(io,event.target.value)}>
  <option value="">No fault</option>{kinds.map(kind=><option key={kind} value={kind}>{FAULT_LABEL[kind]}</option>)}</select>;
 return <aside className="simulation-panel" data-testid="simulation-panel">
  <small>SIMULATION</small>
  <p className="sim-label" data-testid="sim-label">{GENERIC_SIMULATION_LABEL}</p>
  {inputs.map(io=><div className="sim-io" key={io.id}>
   {io.value==="bool"?<label className="sim-fault"><input type="checkbox" data-testid={`sim-input-${io.id}`} checked={!!values[io.id]} onChange={event=>setValues(v=>({...v,[io.id]:event.target.checked}))}/> {io.name} ({io.id}) on</label>
    :<label className="sim-control">{io.name} ({io.id}) <b>{sensed[io.id]===null?"—":`${Number(sensed[io.id]).toFixed(io.value==="celsius"?1:0)} ${io.unit}`}</b>
     <input type="range" min={io.low} max={io.high} step={io.value==="celsius"?.5:1} value={Number(values[io.id])} data-testid={`sim-input-${io.id}`} aria-label={`Simulated ${io.id}`} onChange={event=>setValues(v=>({...v,[io.id]:Number(event.target.value)}))}/></label>}
   {faultSelect(io,INPUT_FAULTS)}</div>)}
  <ul className="sim-outputs">{outputs.map(io=><li key={io.id} className={`sim-state ${Number(shown.outputs[io.id])>0?"on":"off"}`}>
   <span data-testid={`sim-output-${io.id}`}>{io.id} <b>{outputText(shown.outputs[io.id])}</b></span><span>{io.name} · GPIO{io.gpio}</span>{faultSelect(io,OUTPUT_FAULTS)}</li>)}</ul>
  {shown.warnings.length>0&&<ul className="sim-warnings" role="alert" data-testid="sim-warnings">{shown.warnings.map(text=><li key={text}>{text}</li>)}</ul>}
  {!rules.length&&<p className="sim-note">No control rules: outputs stay at their start value.</p>}
  <p className="sim-note">3D motion is an animation of the simulated output, not a measured movement.</p>
 </aside>;
}
