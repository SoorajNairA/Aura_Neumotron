import {useEffect,useState} from "react";
import {TestBench} from "./TestBench";
import {hasStudioModel} from "./studioModels";
import {CheckRow,GROUP_ROLE,PICKABLE_GPIOS,PinRef,checksForComponent,componentGroup,connectionRows,partDescription,partNumber} from "./studio";

type Props={componentId:string;label:string;family?:string;graph:{entities:any[]}|undefined;findings:any[];thumbnail?:string;onShowConnections:()=>void;onChangePin?:(pin:PinRef,gpio:number)=>Promise<string|undefined>;onChangeParameter?:(componentId:string,key:string,value:string|number|boolean)=>Promise<string|undefined>;connectTools?:ConnectTools;benchApi?:string;settingsToken?:string};

type Iface={name:string;kind:string;compatible:string[]};
export type ConnectTools={interfaces:(componentId:string)=>Promise<Iface[]>;connect:(source:{id:string;iface:string},target:{id:string;iface:string})=>Promise<string|undefined>};
// Mirrors the server allowlist: ratings, identity and safety claims are catalogue facts, not settings.
const CONFIGURABLE_PARAMETERS=new Set(["threshold_c"]);

export function ComponentCard({componentId,label,family,graph,findings,thumbnail,onShowConnections,onChangePin,onChangeParameter,connectTools,benchApi,settingsToken}:Props){
 const [paramError,setParamError]=useState<string>();
 const [pinError,setPinError]=useState<string>(),[pinBusy,setPinBusy]=useState(false);
 const changePin=async(pin:PinRef,gpio:number)=>{if(!onChangePin||gpio===pin.gpio)return;setPinBusy(true);setPinError(undefined);try{setPinError(await onChangePin(pin,gpio))}finally{setPinBusy(false)}};
 const entity=graph?.entities?.find(item=>item.id===componentId);
 const kind=family||entity?.metadata?.family;
 const rows=connectionRows(componentId,graph);
 const modelled=kind==="microcontroller_board"?entity?.metadata?.parameters?.component_definition_id==="esp32-devkit-v1":hasStudioModel(kind);
 const dims=entity?.metadata?.dimensions,sizeText=dims?.width&&dims?.length&&dims?.height
  ?`${[dims.width,dims.length,dims.height].map((d:any)=>d.value).join(" × ")} mm${entity?.metadata?.dimensions_qualifier?` (${entity.metadata.dimensions_qualifier})`:""}`:null;
 const [wire,setWire]=useState<string>(),wireRow=rows.find(row=>row.port===wire);
 const settings=Object.entries(entity?.metadata?.parameters||{}).filter(([key,value])=>CONFIGURABLE_PARAMETERS.has(key)&&typeof value==="number") as [string,number][];
 const changeParameter=async(key:string,old:number,raw:string)=>{
  const value=Number(raw);if(!onChangeParameter||raw.trim()===""||!Number.isFinite(value)||value===old)return;
  setParamError(undefined);setParamError(await onChangeParameter(componentId,key,value))};
 const gpio=rows.find(row=>row.value.startsWith("GPIO"));
 // The only derived check: a pin assignment recorded in the graph. Everything else comes from verification findings.
 const checks:CheckRow[]=[...(gpio?[{id:"pin-assigned",title:"Pin assigned",detail:`Connected to ${gpio.value}`,tone:"pass" as const}]:[]),...checksForComponent(componentId,findings)];
 return <div className="component-card">
  <header><div><h2>{label}</h2><p className="part-number">{partNumber(entity)}</p><span className="role-chip">{GROUP_ROLE[componentGroup(kind)]}</span></div>
   {thumbnail?<img src={thumbnail} alt=""/>:<span className={`card-icon icon-${componentGroup(kind).toLowerCase()}`} aria-hidden="true"/>}</header>
  {partDescription(entity)&&<p className="part-description">{partDescription(entity)}</p>}
  {sizeText&&<p className="part-size" data-testid="part-size">Size {sizeText}</p>}
  {!modelled&&<p className="proxy-label" data-testid="proxy-label">Generic proxy — no detailed 3D model for this part yet</p>}
  <h3 className="card-heading">Connection</h3>
  {!graph?<p className="empty-copy" data-testid="connection-rows">Loading connections…</p>:rows.length?<ul className="connection-rows" data-testid="connection-rows">{rows.map(row=><li key={row.port}><span className={`pin-dot tone-${row.tone}`} aria-hidden="true"/><button className="wire-row" aria-pressed={wire===row.port} onClick={()=>setWire(wire===row.port?undefined:row.port)}>{row.label}{row.polarity&&row.polarity!=="signal"?` (${row.polarity})`:""}{row.header&&<small> {row.header}</small>}</button>{row.pin&&onChangePin?<select aria-label={`Change pin for ${row.label}`} value={String(row.pin.gpio)} disabled={pinBusy} onChange={event=>changePin(row.pin!,Number(event.target.value))}>{[...new Set([row.pin.gpio,...PICKABLE_GPIOS])].map(pin=><option key={pin} value={pin}>GPIO {pin}</option>)}</select>:<b>{row.value}</b>}</li>)}</ul>
   :<p className="empty-copy" data-testid="connection-rows">No electrical connections in the graph.</p>}
  {wireRow?.endpoints&&<p className="wire-endpoints" data-testid="wire-endpoints"><span>{wireRow.endpoints[0]}</span><span aria-hidden="true">↔</span><span>{wireRow.endpoints[1]}</span></p>}
  {pinError&&<p className="pin-error" role="alert" data-testid="pin-error">{pinError}</p>}
  {settings.length>0&&onChangeParameter&&<><h3 className="card-heading">Settings</h3><ul className="part-settings" data-testid="part-settings">{settings.map(([key,value])=><li key={key}><label>{key.replace(/_/g," ")}
   {/* Re-seeded from the graph whenever the value or the pending proposal changes; Enter is the only submit. */}
   <input key={`${value}-${settingsToken}`} aria-label={key} type="number" defaultValue={String(value)} onKeyDown={e=>{if(e.key==="Enter")changeParameter(key,value,(e.target as HTMLInputElement).value)}}/></label></li>)}</ul>
   {paramError&&<p className="pin-error" role="alert" data-testid="param-error">{paramError}</p>}</>}
  <h3 className="card-heading">Design checks</h3>
  {checks.length?<ul className="component-checks" data-testid="component-checks">{checks.slice(0,6).map(check=><li key={check.id} className={`check-${check.tone}`}><span className="check-mark" aria-hidden="true">{check.tone==="pass"?"✓":check.tone==="fail"?"✕":"!"}</span><div><b>{check.title}</b><small>{check.detail}</small></div></li>)}</ul>
   :<p className="empty-copy" data-testid="component-checks">No checks reference this component.</p>}
  {benchApi!==undefined&&<TestBench key={`bench-${componentId}`} api={benchApi} family={kind} definitionId={entity?.metadata?.parameters?.component_definition_id}/>}
  {connectTools&&graph&&<ConnectForm key={`connect-${componentId}`} componentId={componentId} graph={graph} tools={connectTools}/>}
  <button className="show-connections" onClick={onShowConnections}>Show connections</button>
 </div>;
}

// Mount this part onto another part's compatible interface; the backend's attachment rules decide.
function ConnectForm({componentId,graph,tools}:{componentId:string;graph:{entities:any[]};tools:ConnectTools}){
 const [open,setOpen]=useState(false),[mine,setMine]=useState<Iface[]>([]),[theirs,setTheirs]=useState<Iface[]>([]);
 const [from,setFrom]=useState(""),[other,setOther]=useState(""),[to,setTo]=useState(""),[error,setError]=useState<string>(),[busy,setBusy]=useState(false);
 useEffect(()=>{if(open)tools.interfaces(componentId).then(setMine).catch(()=>setError("Interfaces could not load."))},[open,componentId]);
 useEffect(()=>{setTheirs([]);setTo("");if(other)tools.interfaces(other).then(setTheirs).catch(()=>setError("Interfaces could not load."))},[other]);
 const fromKind=mine.find(item=>item.name===from)?.kind;
 const matches=theirs.filter(item=>fromKind&&item.compatible.includes(fromKind));
 useEffect(()=>{setTo(matches[0]?.name||"")},[from,theirs]);
 const parts=graph.entities.filter(item=>item.kind==="component"&&item.id!==componentId);
 if(!open)return <button className="connect-open" onClick={()=>setOpen(true)}>Connect…</button>;
 return <div className="connect-form" data-testid="connect-form">
  <label>From<select aria-label="Connect from interface" value={from} onChange={e=>setFrom(e.target.value)}><option value="">Choose…</option>{mine.map(item=><option key={item.name} value={item.name}>{item.name}</option>)}</select></label>
  <label>To part<select aria-label="Connect to component" value={other} onChange={e=>setOther(e.target.value)}><option value="">Choose…</option>{parts.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
  <label>To interface<select aria-label="Connect to interface" value={to} onChange={e=>setTo(e.target.value)} disabled={!matches.length}>{matches.map(item=><option key={item.name} value={item.name}>{item.name}</option>)}</select></label>
  {from&&other&&theirs.length>0&&!matches.length&&<p className="empty-copy">No compatible interface on that part.</p>}
  <button className="primary" disabled={!from||!other||!to||busy} onClick={async()=>{setBusy(true);setError(undefined);try{setError(await tools.connect({id:other,iface:to},{id:componentId,iface:from}))}finally{setBusy(false)}}}>Propose connection</button>
  {error&&<p className="pin-error" role="alert" data-testid="connect-error">{error}</p>}
 </div>;
}
