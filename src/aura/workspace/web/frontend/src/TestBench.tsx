import {useEffect,useState} from "react";
import {BENCH_LABEL,DS18B20_DISCONNECTED,benchKind,ds18b20Reading} from "./benches";
import {factLabel,Fact} from "./libraryHelpers";

export function TestBench({api,family,definitionId}:{api:string;family?:string;definitionId?:string}){
 const kind=benchKind(family,definitionId);
 return <section className="test-bench" data-testid="test-bench"><h3 className="card-heading">Test bench</h3>
  {kind==="ds18b20"?<SensorBench/>:kind==="fan"?<FanBench api={api} definitionId={definitionId}/>:<p className="empty-copy">No test bench yet</p>}
  {kind&&<small className="bench-label">{BENCH_LABEL}</small>}
 </section>;
}

function SensorBench(){
 const [temp,setTemp]=useState(25),[disconnected,setDisconnected]=useState(false);
 const reading=ds18b20Reading(temp,!disconnected);
 return <div className="bench-body">
  <label>Temperature<input type="number" step="0.01" aria-label="Bench temperature" value={temp} onChange={e=>setTemp(Number(e.target.value))}/></label>
  <input type="range" min={-55} max={125} step={0.5} aria-hidden="true" tabIndex={-1} value={temp} onChange={e=>setTemp(Number(e.target.value))}/>
  <label><input type="checkbox" aria-label="Disconnect sensor" checked={disconnected} onChange={e=>setDisconnected(e.target.checked)}/> Disconnect sensor</label>
  <p>Reading <b data-testid="bench-reading">{reading===DS18B20_DISCONNECTED?`${DS18B20_DISCONNECTED} (sensor fault)`:`${reading.toFixed(4)} °C`}</b></p>
 </div>;
}

function FanBench({api,definitionId}:{api:string;definitionId?:string}){
 const [on,setOn]=useState(false),[current,setCurrent]=useState<Fact>();
 useEffect(()=>{if(definitionId)fetch(`${api}/api/catalogue/${definitionId}`).then(r=>r.ok?r.json():undefined).then(item=>setCurrent(item?.properties?.current)).catch(()=>undefined)},[api,definitionId]);
 return <div className="bench-body">
  <label><input type="checkbox" aria-label="Gate on" checked={on} onChange={e=>setOn(e.target.checked)}/> Gate on</label>
  <p>Fan <b>{on?"Running":"Stopped"}</b></p>
  {on&&<p>{current?`Current ${factLabel(current)} — catalogue value, not measured`:"current not in catalogue"}</p>}
 </div>;
}
