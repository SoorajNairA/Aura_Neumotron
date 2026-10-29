// Pure wiring-view layout: per-part offsets, per-wire segment bends and display-name overrides, applied on top of the
// generated circuit JSON. Electrical connectivity, ids and pin identities are never changed here.
export type PartOffset={dx:number;dy:number};
export type WiringLayout={parts:Record<string,PartOffset>;wires:Record<string,number[]>;labels:Record<string,string>};
export const emptyLayout=():WiringLayout=>({parts:{},wires:{},labels:{}});

type Pt={x:number;y:number};
const EPS=1e-6;
const num=(value:unknown)=>typeof value==="number"&&Number.isFinite(value)?value:0;
const same=(a:Pt,b:Pt)=>Math.abs(a.x-b.x)<EPS&&Math.abs(a.y-b.y)<EPS;
// A zero-length segment counts as horizontal.
const horizontal=(a:Pt,b:Pt)=>Math.abs(a.y-b.y)<=Math.abs(a.x-b.x);
const add=(p:Pt,dx:number,dy:number):Pt=>({x:p.x+dx,y:p.y+dy});
const offsetOf=(layout:WiringLayout,id:string|undefined):PartOffset|undefined=>{
 const entry:any=id?layout.parts[id]:undefined;if(!entry)return;
 const dx=num(entry.dx),dy=num(entry.dy);return dx||dy?{dx,dy}:undefined;
};

// Wire id: the trace's net (or graph connection) id plus its pin pair, sorted so terminal order does not matter. It does
// not depend on how many traces the net has or on the positional schematic_trace_id, which regeneration can reassign.
// Traces without a net and both pins, or whose key is shared by another trace, get no id: they cannot carry bends.
export function traceWireIds(circuit:any[]):Record<string,string>{
 const keyOf=(trace:any):string|undefined=>{
  const connection=trace.aura_connection||{},scope=connection.netId??trace.aura_net_id??connection.graphConnectionId??trace.aura_graph_connection_id;
  if(typeof scope!=="string"||!scope||typeof connection.from!=="string"||!connection.from||typeof connection.to!=="string"||!connection.to)return;
  return `${scope}:${[connection.from,connection.to].sort().join("|")}`;
 };
 const keys=new Map<string,string>(),counts=new Map<string,number>();
 for(const trace of circuit){if(trace?.type!=="schematic_trace"||!trace.schematic_trace_id)continue;const key=keyOf(trace);if(key){keys.set(trace.schematic_trace_id,key);counts.set(key,(counts.get(key)||0)+1)}}
 return Object.fromEntries([...keys].filter(([,key])=>counts.get(key)===1));
}

// One connected run of trace edges. `seg[i]` is the original edge index of segment i (-1 for an inserted connector);
// `pin[i]` marks points that must not move (run ends and junctions) unless their port moves.
type Chain={p:Pt[];seg:number[];pin:boolean[];extra:any[]};
function chainsOf(edges:any[],junctions:Pt[]):Chain[]{
 const chains:Chain[]=[];
 edges.forEach((edge,index)=>{
  const from={x:num(edge?.from?.x),y:num(edge?.from?.y)},to={x:num(edge?.to?.x),y:num(edge?.to?.y)};
  const last=chains.at(-1);
  if(last&&same(last.p.at(-1)!,from)){last.p.push(to);last.seg.push(index);last.pin.push(false);last.extra.push(edge)}
  else chains.push({p:[from,to],seg:[index],pin:[true,false],extra:[edge]});
 });
 for(const chain of chains){chain.pin[chain.pin.length-1]=true;chain.p.forEach((point,i)=>{if(junctions.some(j=>same(j,point)))chain.pin[i]=true})}
 return chains;
}
const insert=(chain:Chain,pointAt:number,point:Pt,segAt:number)=>{chain.p.splice(pointAt,0,point);chain.pin.splice(pointAt,0,false);chain.seg.splice(segAt,0,-1);chain.extra.splice(segAt,0,undefined)};
// Shift segment s perpendicular to itself. A neighbour that is perpendicular simply stretches; otherwise (collinear
// neighbour, pinned point or run end) a connector segment is inserted, so the run stays connected and orthogonal.
function shiftSegment(chain:Chain,s:number,offset:number,moveStart=false){
 const a=chain.p[s],b=chain.p[s+1],h=horizontal(a,b),dx=h?0:offset,dy=h?offset:0;
 const stretches=(i:number,next:number)=>next>=0&&next<chain.p.length&&!chain.pin[i]&&horizontal(chain.p[Math.min(i,next)],chain.p[Math.max(i,next)])!==h;
 if(stretches(s+1,s+2))chain.p[s+1]=add(b,dx,dy);else insert(chain,s+1,add(b,dx,dy),s+1);
 if(moveStart)chain.p[s]=add(a,dx,dy);
 else if(stretches(s,s-1))chain.p[s]=add(a,dx,dy);else{insert(chain,s+1,add(a,dx,dy),s)}
}
// Move the first point of the run by (dx,dy): along the first segment it stretches, across it the segment shifts.
function moveStart(chain:Chain,dx:number,dy:number){
 const h=horizontal(chain.p[0],chain.p[1]);
 chain.p[0]=add(chain.p[0],h?dx:0,h?0:dy);
 const across=h?dy:dx;
 if(Math.abs(across)>EPS)shiftSegment(chain,0,across,true);
}
const reverse=(chain:Chain)=>{chain.p.reverse();chain.pin.reverse();chain.seg.reverse();chain.extra.reverse()};

let keyCache=new WeakMap<WiringLayout,number>();
function layoutKey(layout:WiringLayout){
 let key=keyCache.get(layout);if(key!==undefined)return key;
 const text=JSON.stringify(layout);let hash=7;for(let i=0;i<text.length;i++)hash=(hash*31+text.charCodeAt(i))|0;
 key=1+(hash>>>0);keyCache.set(layout,key);return key;
}

// Circuit JSON with the layout applied. The result carries `editCount` so the schematic viewer re-renders it.
export function applyLayout(circuit:any[],layout:WiringLayout,mapping:Record<string,string>):any[]{
 const moved=new Map<string,PartOffset>();// schematic_component_id → offset
 const labelBySource=new Map<string,string>(),labelByComponent=new Map<string,{label:string;names:Set<string>}>();
 const sources=new Map<string,any>();for(const item of circuit)if(item?.type==="source_component")sources.set(item.source_component_id,item);
 for(const item of circuit){
  if(item?.type!=="schematic_component")continue;
  const semantic=mapping[item.schematic_component_id]??item.aura_semantic_id,offset=offsetOf(layout,semantic);
  if(offset)moved.set(item.schematic_component_id,offset);
  const label=semantic?layout.labels[semantic]:undefined;
  if(typeof label!=="string"||!label.trim())continue;
  if(item.source_component_id)labelBySource.set(item.source_component_id,label.trim());
  // Generated names this part is drawn with; a schematic_text showing one of them is the part's name label.
  const source=sources.get(item.source_component_id);
  labelByComponent.set(item.schematic_component_id,{label:label.trim(),names:new Set([source?.display_name,source?.name,item.symbol_display_value,item.aura_display_name].filter((name):name is string=>typeof name==="string"&&!!name))});
 }
 const movedPorts:{at:Pt;id:string;offset:PartOffset}[]=[];
 for(const item of circuit)if(item?.type==="schematic_port"&&moved.has(item.schematic_component_id)&&item.center)movedPorts.push({at:item.center,id:item.schematic_port_id,offset:moved.get(item.schematic_component_id)!});
 const portAt=(point:Pt,portId?:string)=>movedPorts.find(port=>(portId&&port.id===portId)||same(port.at,point))?.offset;
 const wireIds=traceWireIds(circuit);
 // Net display names: aura net id → connectivity key, so tscircuit net labels show the override too.
 const netKeyLabel=new Map<string,string>();
 for(const item of circuit){const netId=item?.aura_connection?.netId,key=item?.subcircuit_connectivity_map_key,label=netId?layout.labels[netId]:undefined;if(item?.type==="schematic_trace"&&key&&typeof label==="string"&&label.trim())netKeyLabel.set(key,label.trim())}
 const shift=(point:any,offset:PartOffset)=>point&&typeof point==="object"?{...point,x:num(point.x)+offset.dx,y:num(point.y)+offset.dy}:point;
 const out=circuit.map(item=>{
  if(!item||typeof item!=="object")return item;
  if(item.type==="schematic_component"){
   const offset=moved.get(item.schematic_component_id),label=labelBySource.get(item.source_component_id);
   if(!offset&&!label)return item;
   const next={...item};
   if(offset)next.center=shift(item.center,offset);
   if(label){next.symbol_display_value=label;next.aura_display_name=label}
   return next;
  }
  if(item.type==="source_component"){const label=labelBySource.get(item.source_component_id);return label?{...item,display_name:label}:item}
  if(item.type==="schematic_trace"){const id=wireIds[item.schematic_trace_id];return applyTrace(item,id?layout.wires[id]:undefined,portAt)}
  if(item.type==="schematic_net_label"){
   const offset=item.anchor_position?portAt(item.anchor_position):undefined,label=netKeyLabel.get(item.source_net_id);
   if(!offset&&!label)return item;
   const next={...item};if(offset){next.anchor_position=shift(item.anchor_position,offset);if(item.center)next.center=shift(item.center,offset)}if(label)next.text=label;return next;
  }
  const offset=typeof item.type==="string"&&item.type.startsWith("schematic_")&&item.schematic_component_id?moved.get(item.schematic_component_id):undefined;
  const named=item.type==="schematic_text"?labelByComponent.get(item.schematic_component_id):undefined,rename=named&&named.names.has(item.text);
  if(!offset&&!rename)return item;
  const next={...item};
  if(rename)next.text=named!.label;
  if(offset){
   for(const key of ["center","position","anchor_position","start","end"])if(item[key]&&typeof item[key]==="object")next[key]=shift(item[key],offset);
   for(const [x,y] of [["x","y"],["x1","y1"],["x2","y2"]])if(typeof item[x]==="number"&&typeof item[y]==="number"){next[x]=item[x]+offset.dx;next[y]=item[y]+offset.dy}
   if(Array.isArray(item.points))next.points=item.points.map((point:any)=>shift(point,offset));
  }
  return next;
 });
 (out as any).editCount=layoutKey(layout);
 return out;
}

function applyTrace(trace:any,bends:unknown,portAt:(point:Pt,portId?:string)=>PartOffset|undefined){
 const edges=Array.isArray(trace.edges)?trace.edges:[];
 const offsets=Array.isArray(bends)?bends.map(num):[];
 const junctions:Pt[]=Array.isArray(trace.junctions)?trace.junctions:[];
 // A run that passes through a moved pin (a T at the pin) is split there, so that point moves with the pin like a
 // run end and stays on the junction dot that moves with it.
 const chains:Chain[]=[];
 for(const chain of chainsOf(edges,junctions)){
  let rest=chain,k=1;
  while(k<rest.p.length-1){
   if(!portAt(rest.p[k])){k++;continue}
   chains.push({p:rest.p.slice(0,k+1),seg:rest.seg.slice(0,k),pin:[...rest.pin.slice(0,k),true],extra:rest.extra.slice(0,k)});
   rest={p:rest.p.slice(k),seg:rest.seg.slice(k),pin:[true,...rest.pin.slice(k+1)],extra:rest.extra.slice(k)};k=1;
  }
  chains.push(rest);
 }
 const startOffsets=chains.map(chain=>portAt(chain.p[0],chain.extra[0]?.from_schematic_port_id)),endOffsets=chains.map(chain=>portAt(chain.p.at(-1)!,chain.extra.at(-1)?.to_schematic_port_id));
 let changed=false;
 chains.forEach((chain,c)=>{
  offsets.forEach((offset,index)=>{const s=chain.seg.indexOf(index);if(s>=0&&Math.abs(offset)>EPS){shiftSegment(chain,s,offset);changed=true}});
  const start=startOffsets[c],end=endOffsets[c];
  if(start){moveStart(chain,start.dx,start.dy);changed=true}
  if(end){reverse(chain);moveStart(chain,end.dx,end.dy);reverse(chain);changed=true}
 });
 if(!changed)return trace;
 const nextEdges:any[]=[];
 for(const chain of chains)chain.seg.forEach((index,s)=>{
  const base=index>=0?chain.extra[s]:{};
  nextEdges.push({...base,from:{x:chain.p[s].x,y:chain.p[s].y},to:{x:chain.p[s+1].x,y:chain.p[s+1].y},...(index>=0?{aura_segment_index:index}:{})});
 });
 const nextJunctions=junctions.map(point=>{const offset=portAt(point);return offset?add(point,offset.dx,offset.dy):point});
 return {...trace,edges:nextEdges,junctions:nextJunctions};
}

// Ids whose entries survive a regeneration; everything else is dropped. `partIds` covers part offsets and labels
// (component semantic ids and net ids), `wireIds` covers bends.
export function pruneLayout(layout:WiringLayout,partIds:Set<string>,wireIds:Set<string>):WiringLayout{
 const keep=<T>(record:Record<string,T>,ids:Set<string>)=>Object.fromEntries(Object.entries(record||{}).filter(([id])=>ids.has(id)));
 return {parts:keep(layout.parts,partIds),wires:keep(layout.wires,wireIds),labels:keep(layout.labels,partIds)};
}

export type LayoutHistory={layout:WiringLayout;past:WiringLayout[];future:WiringLayout[]};
export type LayoutAction=
 |{type:"move";id:string;dx:number;dy:number}
 |{type:"bend";wire:string;index:number;delta:number}
 |{type:"rename";id:string;label:string}
 |{type:"undo"}|{type:"redo"}
 |{type:"load";layout:WiringLayout}
 |{type:"prune";partIds:Set<string>;wireIds:Set<string>};
const HISTORY_LIMIT=100;
const round=(value:number)=>Math.round(value*1e6)/1e6;
const commit=(state:LayoutHistory,layout:WiringLayout):LayoutHistory=>({layout,past:[...state.past,state.layout].slice(-HISTORY_LIMIT),future:[]});

export function layoutReducer(state:LayoutHistory,action:LayoutAction):LayoutHistory{
 const layout=state.layout;
 switch(action.type){
  case "move":{
   if(!num(action.dx)&&!num(action.dy))return state;
   const current:any=layout.parts[action.id]||{};
   return commit(state,{...layout,parts:{...layout.parts,[action.id]:{dx:round(num(current.dx)+num(action.dx)),dy:round(num(current.dy)+num(action.dy))}}});
  }
  case "bend":{
   if(!num(action.delta)||!(action.index>=0))return state;
   const list=Array.isArray(layout.wires[action.wire])?[...layout.wires[action.wire]].map(num):[];
   while(list.length<=action.index)list.push(0);
   list[action.index]=round(list[action.index]+num(action.delta));
   return commit(state,{...layout,wires:{...layout.wires,[action.wire]:list}});
  }
  case "rename":{
   const label=action.label.trim(),labels={...layout.labels};
   if((labels[action.id]??"")===label)return state;
   if(label)labels[action.id]=label;else delete labels[action.id];
   return commit(state,{...layout,labels});
  }
  case "undo":{
   if(!state.past.length)return state;
   return {layout:state.past.at(-1)!,past:state.past.slice(0,-1),future:[layout,...state.future]};
  }
  case "redo":{
   if(!state.future.length)return state;
   return {layout:state.future[0],past:[...state.past,layout],future:state.future.slice(1)};
  }
  case "load":return {layout:action.layout,past:[],future:[]};
  case "prune":{
   const prune=(value:WiringLayout)=>pruneLayout(value,action.partIds,action.wireIds);
   const size=(value:WiringLayout)=>Object.keys(value.parts).length+Object.keys(value.wires).length+Object.keys(value.labels).length;
   if([layout,...state.past,...state.future].every(value=>size(prune(value))===size(value)))return state;
   return {layout:prune(layout),past:state.past.map(prune),future:state.future.map(prune)};
  }
 }
}
