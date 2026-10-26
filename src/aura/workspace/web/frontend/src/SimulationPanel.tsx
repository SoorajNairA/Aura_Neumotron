import {useEffect,useRef,useState} from "react";
import {fanControl,FanReason} from "./fanControl";

export type CompileInfo={status:"passed"|"failed"|"toolchain_missing";revisionId:string;sizeBytes?:number|null;missing?:string|null;errors?:{file?:string|null;line?:number|null;message:string}[]};
export type FirmwareInfo={supported:boolean;reasons:string[];tOnC?:number;tOffC?:number;pins?:Record<string,number>;revisionId?:string|null;source?:string;lastCompile?:CompileInfo|null;lastCompileCurrent?:boolean};


export const SIMULATION_LABEL="Behavioral simulation — control logic only. Not electrical verification, not firmware execution.";
const REASON_TEXT:Record<FanReason,string>={above_on:"at or above on threshold",below_off:"at or below off threshold",in_band:"inside hysteresis band, state held",sensor_fault:"sensor fault, fail-safe on"};
const PIN_LABEL:Record<string,string>={temperature_data:"DS18B20 data",fan_gate:"MOSFET gate"};

export type FanSimulation=ReturnType<typeof useFanSimulation>;

// One simulation state shared by the Simulation space and the inspector preview card.
export function useFanSimulation(firmware:FirmwareInfo|undefined){
 const tOn=firmware?.tOnC??26,tOff=firmware?.tOffC??24;
 // The slider always spans both thresholds, even for designs outside a typical room range.
 const minC=Math.min(10,Math.floor(tOff)-5),maxC=Math.max(40,Math.ceil(tOn)+5);
 const [temperature,setTemperature]=useState(tOff-1),[fault,setFault]=useState(false),[on,setOn]=useState(false),[reason,setReason]=useState<FanReason>("below_off");
 const [log,setLog]=useState<{time:string;text:string}[]>([]);
 const previous=useRef(false);
 // Each project revision starts fresh, just below its own off threshold.
 useEffect(()=>{previous.current=false;setTemperature(tOff-1);setFault(false);setLog([]);setOn(false);setReason("below_off")},[firmware?.revisionId,tOff]);
 useEffect(()=>{
  if(!firmware?.supported){previous.current=false;setOn(false);return}
  const result=fanControl(previous.current,fault?null:temperature,tOn,tOff);
  if(result.on!==previous.current||result.reason==="sensor_fault")setLog(entries=>[{time:new Date().toLocaleTimeString(),text:`${fault?"sensor fault":`${temperature.toFixed(1)} °C`} → fan ${result.on?"ON":"OFF"} (${REASON_TEXT[result.reason]})`},...entries].slice(0,50));
  previous.current=result.on;setOn(result.on);setReason(result.reason);
 },[temperature,fault,tOn,tOff,firmware?.supported]);
 return {tOn,tOff,minC,maxC,temperature,setTemperature,fault,setFault,on,reason,reasonText:REASON_TEXT[reason],log};
}

export function SimulationPreview({sim}:{sim:FanSimulation}){
 return <section className="sim-preview" data-testid="sim-preview">
  <header><b>Simulation preview</b><span className={sim.on?"dot on":"dot"} aria-hidden="true"/></header>
  <div className="sim-preview-body"><div><small>Simulated input</small><strong>{sim.fault?"—":`${sim.temperature.toFixed(1)} °C`}</strong>
   <input type="range" min={sim.minC} max={sim.maxC} step={0.5} value={sim.temperature} disabled={sim.fault} aria-label="Preview temperature" onChange={event=>sim.setTemperature(Number(event.target.value))}/>
   <span className="sim-range"><span>{sim.minC} °C</span><span>{sim.maxC} °C</span></span></div>
   <div><small>Fan status</small><p className={sim.on?"fan-on":"fan-off"}>{sim.on?"Fan on":"Fan off"}</p><span className="sim-reason">({sim.reasonText})</span></div></div>
 </section>;
}

export function SimulationPanel({firmware,sim}:{firmware:FirmwareInfo;sim:FanSimulation}){
 const {tOn,tOff,minC,maxC,temperature,setTemperature,fault,setFault,on,log}=sim,reason=sim.reason;
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
  <p className="sim-note">Firmware for these thresholds is in the Code space.</p>
  <p className="sim-note">3D fan spin is an animation of the simulated output, not a measured movement.</p>
  <ol className="sim-log" data-testid="sim-log">{log.map((entry,index)=><li key={`${entry.time}-${log.length-index}`}><time>{entry.time}</time>{entry.text}</li>)}</ol>
 </aside>;
}
