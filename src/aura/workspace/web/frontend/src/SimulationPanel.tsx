import {useEffect,useRef,useState} from "react";
import {fanControl,FanReason} from "./fanControl";

export type CompileInfo={status:"passed"|"failed"|"toolchain_missing";revisionId:string;sizeBytes?:number|null;missing?:string|null;errors?:{file?:string|null;line?:number|null;message:string}[]};
export type FirmwareInfo={supported:boolean;reasons:string[];tOnC?:number;tOffC?:number;pins?:Record<string,number>;revisionId?:string|null;source?:string;lastCompile?:CompileInfo|null;lastCompileCurrent?:boolean};

const compileText=(result:CompileInfo)=>result.status==="passed"?`Compiled for ESP32${result.sizeBytes?` (${result.sizeBytes.toLocaleString()} bytes)`:""}`
 :result.status==="toolchain_missing"?`Toolchain missing: ${result.missing||"unknown"}`
 :`Compile failed: ${result.errors?.[0]?.message||"see compiler output"}${result.errors?.[0]?.line?` (line ${result.errors[0].line})`:""}`;

export const SIMULATION_LABEL="Behavioral simulation — control logic only. Not electrical verification, not firmware execution.";
const REASON_TEXT:Record<FanReason,string>={above_on:"at or above on threshold",below_off:"at or below off threshold",in_band:"inside hysteresis band, state held",sensor_fault:"sensor fault, fail-safe on"};
const PIN_LABEL:Record<string,string>={temperature_data:"DS18B20 data",fan_gate:"MOSFET gate"};

export function SimulationPanel({firmware,onFanChange,compile}:{firmware:FirmwareInfo;onFanChange:(on:boolean)=>void;compile:()=>Promise<CompileInfo>}){
 const tOn=firmware.tOnC??26,tOff=firmware.tOffC??24;
 // The slider always spans both thresholds, even for designs outside a typical room range.
 const minC=Math.min(10,Math.floor(tOff)-5),maxC=Math.max(40,Math.ceil(tOn)+5);
 const [compileResult,setCompileResult]=useState<CompileInfo|null>(firmware.lastCompile??null),[compileCurrent,setCompileCurrent]=useState(!!firmware.lastCompileCurrent);
 const [compiling,setCompiling]=useState(false),[compileError,setCompileError]=useState("");
 const runCompile=async()=>{setCompiling(true);setCompileError("");try{const result=await compile();setCompileResult(result);setCompileCurrent(result.revisionId===firmware.revisionId)}catch(error){setCompileError((error as Error).message)}finally{setCompiling(false)}};
 const firmwareStatus=compiling?"Compiling…":compileError?`Compile request failed: ${compileError}`:!compileResult?"Not compiled yet":
  `${compileText(compileResult)}${compileCurrent?"":" — compiled for an earlier revision, not the current design revision"}`;
 const [temperature,setTemperature]=useState(tOff-1),[fault,setFault]=useState(false),[on,setOn]=useState(false),[reason,setReason]=useState<FanReason>("below_off");
 const [log,setLog]=useState<{time:string;text:string}[]>([]);
 const previous=useRef(false);
 useEffect(()=>{
  const result=fanControl(previous.current,fault?null:temperature,tOn,tOff);
  if(result.on!==previous.current||result.reason==="sensor_fault")setLog(entries=>[{time:new Date().toLocaleTimeString(),text:`${fault?"sensor fault":`${temperature.toFixed(1)} °C`} → fan ${result.on?"ON":"OFF"} (${REASON_TEXT[result.reason]})`},...entries].slice(0,50));
  previous.current=result.on;setOn(result.on);setReason(result.reason);onFanChange(result.on);
 },[temperature,fault,tOn,tOff]);
 useEffect(()=>()=>onFanChange(false),[]);
 return <aside className="simulation-panel" data-testid="simulation-panel">
  <small>SIMULATION</small>
  <p className="sim-label" data-testid="sim-label">{SIMULATION_LABEL}</p>
  <label className="sim-control">Temperature <b>{fault?"—":`${temperature.toFixed(1)} °C`}</b>
   <input type="range" min={minC} max={maxC} step={0.5} value={temperature} disabled={fault} data-testid="sim-temperature" aria-label="Simulated temperature" onChange={event=>setTemperature(Number(event.target.value))}/>
  </label>
  <label className="sim-fault"><input type="checkbox" checked={fault} data-testid="sim-fault" onChange={event=>setFault(event.target.checked)}/> Inject sensor disconnect</label>
  <div className={`sim-state ${on?"on":"off"}`}>Fan <b data-testid="sim-fan-state">{on?"ON":"OFF"}</b><span>{REASON_TEXT[reason]}</span></div>
  <dl className="sim-facts"><dt>On at</dt><dd>≥ {tOn.toFixed(1)} °C</dd><dt>Off at</dt><dd>≤ {tOff.toFixed(1)} °C</dd>
   {Object.entries(firmware.pins||{}).flatMap(([name,pin])=>[<dt key={`${name}-t`}>{PIN_LABEL[name]||name}</dt>,<dd key={`${name}-d`}>GPIO{pin}</dd>])}</dl>
  <section className="sim-firmware"><div><b>Firmware</b><button onClick={runCompile} disabled={compiling}>COMPILE</button></div>
   <p data-testid="fw-status" className={compileResult?.status==="passed"&&compileCurrent?"tone-pass":compileResult?"tone-warn":""}>{firmwareStatus}</p>
   {firmware.source&&<details><summary>View generated sketch</summary><pre data-testid="fw-source">{firmware.source}</pre></details>}
  </section>
  <p className="sim-note">3D fan spin is an animation of the simulated output, not a measured movement.</p>
  <ol className="sim-log" data-testid="sim-log">{log.map((entry,index)=><li key={index}><time>{entry.time}</time>{entry.text}</li>)}</ol>
 </aside>;
}
