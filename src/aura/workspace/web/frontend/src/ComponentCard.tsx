import {useState} from "react";
import {CheckRow,GROUP_ROLE,PICKABLE_GPIOS,PinRef,checksForComponent,componentGroup,connectionRows,partDescription,partNumber} from "./studio";

type Props={componentId:string;label:string;family?:string;graph:{entities:any[]}|undefined;findings:any[];thumbnail?:string;onShowConnections:()=>void;onChangePin?:(pin:PinRef,gpio:number)=>Promise<string|undefined>;onChangeParameter?:(componentId:string,key:string,value:string|number|boolean)=>Promise<string|undefined>};

const HIDDEN_PARAMETERS=new Set(["component_definition_id","component_definition_version","gpio_map"]);

export function ComponentCard({componentId,label,family,graph,findings,thumbnail,onShowConnections,onChangePin,onChangeParameter}:Props){
 const [paramError,setParamError]=useState<string>();
 const [pinError,setPinError]=useState<string>(),[pinBusy,setPinBusy]=useState(false);
 const changePin=async(pin:PinRef,gpio:number)=>{if(!onChangePin||gpio===pin.gpio)return;setPinBusy(true);setPinError(undefined);try{setPinError(await onChangePin(pin,gpio))}finally{setPinBusy(false)}};
 const entity=graph?.entities?.find(item=>item.id===componentId);
 const kind=family||entity?.metadata?.family;
 const rows=connectionRows(componentId,graph);
 const settings=Object.entries(entity?.metadata?.parameters||{}).filter(([key,value])=>!HIDDEN_PARAMETERS.has(key)&&["string","number","boolean"].includes(typeof value)) as [string,string|number|boolean][];
 const changeParameter=async(key:string,old:string|number|boolean,raw:string|boolean)=>{
  const value=typeof old==="number"?Number(raw):raw;if(!onChangeParameter||value===old||(typeof value==="number"&&!Number.isFinite(value)))return;
  setParamError(undefined);setParamError(await onChangeParameter(componentId,key,value))};
 const gpio=rows.find(row=>row.value.startsWith("GPIO"));
 // The only derived check: a pin assignment recorded in the graph. Everything else comes from verification findings.
 const checks:CheckRow[]=[...(gpio?[{id:"pin-assigned",title:"Pin assigned",detail:`Connected to ${gpio.value}`,tone:"pass" as const}]:[]),...checksForComponent(componentId,findings)];
 return <div className="component-card">
  <header><div><h2>{label}</h2><p className="part-number">{partNumber(entity)}</p><span className="role-chip">{GROUP_ROLE[componentGroup(kind)]}</span></div>
   {thumbnail?<img src={thumbnail} alt=""/>:<span className={`card-icon icon-${componentGroup(kind).toLowerCase()}`} aria-hidden="true"/>}</header>
  {partDescription(entity)&&<p className="part-description">{partDescription(entity)}</p>}
  <h3 className="card-heading">Connection</h3>
  {!graph?<p className="empty-copy" data-testid="connection-rows">Loading connections…</p>:rows.length?<ul className="connection-rows" data-testid="connection-rows">{rows.map(row=><li key={row.port}><span className={`pin-dot tone-${row.tone}`} aria-hidden="true"/><span>{row.label}</span>{row.pin&&onChangePin?<select aria-label={`Change pin for ${row.label}`} value={String(row.pin.gpio)} disabled={pinBusy} onChange={event=>changePin(row.pin!,Number(event.target.value))}>{[...new Set([row.pin.gpio,...PICKABLE_GPIOS])].map(pin=><option key={pin} value={pin}>GPIO {pin}</option>)}</select>:<b>{row.value}</b>}</li>)}</ul>
   :<p className="empty-copy" data-testid="connection-rows">No electrical connections in the graph.</p>}
  {pinError&&<p className="pin-error" role="alert" data-testid="pin-error">{pinError}</p>}
  {settings.length>0&&onChangeParameter&&<><h3 className="card-heading">Settings</h3><ul className="part-settings" data-testid="part-settings">{settings.map(([key,value])=><li key={key}><label>{key.replace(/_/g," ")}
   {typeof value==="boolean"?<input type="checkbox" aria-label={key} defaultChecked={value} onChange={e=>changeParameter(key,value,e.target.checked)}/>
   :<input aria-label={key} type={typeof value==="number"?"number":"text"} defaultValue={String(value)} onBlur={e=>changeParameter(key,value,e.target.value)} onKeyDown={e=>{if(e.key==="Enter")changeParameter(key,value,(e.target as HTMLInputElement).value)}}/>}</label></li>)}</ul>
   {paramError&&<p className="pin-error" role="alert" data-testid="param-error">{paramError}</p>}</>}
  <h3 className="card-heading">Design checks</h3>
  {checks.length?<ul className="component-checks" data-testid="component-checks">{checks.slice(0,6).map(check=><li key={check.id} className={`check-${check.tone}`}><span className="check-mark" aria-hidden="true">{check.tone==="pass"?"✓":check.tone==="fail"?"✕":"!"}</span><div><b>{check.title}</b><small>{check.detail}</small></div></li>)}</ul>
   :<p className="empty-copy" data-testid="component-checks">No checks reference this component.</p>}
  <button className="show-connections" onClick={onShowConnections}>Show connections</button>
 </div>;
}
