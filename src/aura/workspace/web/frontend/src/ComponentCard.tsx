import {CheckRow,GROUP_ROLE,checksForComponent,componentGroup,connectionRows,partDescription,partNumber} from "./studio";

type Props={componentId:string;label:string;family?:string;graph:{entities:any[]}|undefined;findings:any[];thumbnail?:string;onShowConnections:()=>void};

export function ComponentCard({componentId,label,family,graph,findings,thumbnail,onShowConnections}:Props){
 const entity=graph?.entities?.find(item=>item.id===componentId);
 const kind=family||entity?.metadata?.family;
 const rows=connectionRows(componentId,graph);
 const gpio=rows.find(row=>row.value.startsWith("GPIO"));
 // The only derived check: a pin assignment recorded in the graph. Everything else comes from verification findings.
 const checks:CheckRow[]=[...(gpio?[{id:"pin-assigned",title:"Pin assigned",detail:`Connected to ${gpio.value}`,tone:"pass" as const}]:[]),...checksForComponent(componentId,findings)];
 return <div className="component-card">
  <header><div><h2>{label}</h2><p className="part-number">{partNumber(entity)}</p><span className="role-chip">{GROUP_ROLE[componentGroup(kind)]}</span></div>
   {thumbnail?<img src={thumbnail} alt=""/>:<span className={`card-icon icon-${componentGroup(kind).toLowerCase()}`} aria-hidden="true"/>}</header>
  {partDescription(entity)&&<p className="part-description">{partDescription(entity)}</p>}
  <h3 className="card-heading">Connection</h3>
  {!graph?<p className="empty-copy" data-testid="connection-rows">Loading connections…</p>:rows.length?<ul className="connection-rows" data-testid="connection-rows">{rows.map(row=><li key={row.port}><span className={`pin-dot tone-${row.tone}`} aria-hidden="true"/><span>{row.label}</span><b>{row.value}</b></li>)}</ul>
   :<p className="empty-copy" data-testid="connection-rows">No electrical connections in the graph.</p>}
  <h3 className="card-heading">Design checks</h3>
  {checks.length?<ul className="component-checks" data-testid="component-checks">{checks.slice(0,6).map(check=><li key={check.id} className={`check-${check.tone}`}><span className="check-mark" aria-hidden="true">{check.tone==="pass"?"✓":check.tone==="fail"?"✕":"!"}</span><div><b>{check.title}</b><small>{check.detail}</small></div></li>)}</ul>
   :<p className="empty-copy" data-testid="component-checks">No checks reference this component.</p>}
  <button className="show-connections" onClick={onShowConnections}>Show connections</button>
 </div>;
}
