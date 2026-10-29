import {lazy,Suspense,useCallback,useEffect,useMemo,useRef,useState} from "react";
import {applyLayout,layoutReducer,traceWireIds,type LayoutAction,type WiringLayout} from "./wiringLayout";

const SchematicViewer=lazy(()=>import("@tscircuit/schematic-viewer").then(module=>({default:module.SchematicViewer})));

// circuit-to-svg's real→svg projection: x' = a·x + e, y' = d·y + f (d < 0: circuit y points up).
type Projection={a:number;d:number;e:number;f:number;w:number;h:number};
type Drag=
 |{kind:"pan";x:number;y:number;cx:number;cy:number}
 |{kind:"part";id:string;x:number;y:number;toSvg:DOMMatrix;r:Projection;moved:boolean;dx:number;dy:number}
 |{kind:"bend";wire:string;index:number;horizontal:boolean;x:number;y:number;toSvg:DOMMatrix;r:Projection;moved:boolean;delta:number};
type Props={circuit:any[];mapping:Record<string,string>;nets?:any[];selectedNet?:string|null;selectedId?:string|null;layout:WiringLayout;
 dispatch:(action:LayoutAction)=>void;canUndo:boolean;canRedo:boolean;onSelect:(id:string)=>void;onSelectNet?:(id:string)=>void};

const SNAP=.1,START_PX=3,WIRE_HIT_PX=6;
const snap=(value:number)=>Math.round(value/SNAP)*SNAP;
const parseProjection=(svg:SVGSVGElement):Projection|undefined=>{
 const values=(svg.getAttribute("data-real-to-screen-transform")||"").match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi)?.map(Number);
 if(!values||values.length<6||!values[0]||!values[3])return;
 return {a:values[0],d:values[3],e:values[4],f:values[5],w:svg.width.baseVal.value,h:svg.height.baseVal.value};
};
const segmentDistance=(p:{x:number;y:number},a:{x:number;y:number},b:{x:number;y:number})=>{
 const vx=b.x-a.x,vy=b.y-a.y,len=vx*vx+vy*vy,t=len?Math.max(0,Math.min(1,((p.x-a.x)*vx+(p.y-a.y)*vy)/len)):0;
 return Math.hypot(p.x-(a.x+t*vx),p.y-(a.y+t*vy));
};

// Wiring view: tscircuit's read-only viewer renders `applyLayout(circuit, layout)`; dragging, bending, undo and redo are
// handled here. A projection anchor keeps the drawing still while the viewer refits its bounds after an edit.
export function SchematicEditor({circuit,mapping,nets=[],selectedNet,selectedId,layout,dispatch,canUndo,canRedo,onSelect,onSelectNet}:Props){
 const camera=useRef({x:0,y:0,scale:1}),drag=useRef<Drag>(),viewport=useRef<HTMLDivElement>(null),layer=useRef<HTMLDivElement>(null),anchor=useRef<HTMLDivElement>(null);
 const [mode,setMode]=useState<"select"|"pan">("select"),[spaceHeld,setSpaceHeld]=useState(false),[selectedWire,setSelectedWire]=useState<string|null>(null),[preview,setPreview]=useState<WiringLayout>();
 const [projection,setProjection]=useState<Projection>();
 const reference=useRef<Projection>(),resetReference=useRef(true);
 const shown=preview??layout;
 const applied=useMemo(()=>applyLayout(circuit,shown,mapping),[circuit,shown,mapping]);
 const wireIds=useMemo(()=>traceWireIds(circuit),[circuit]);
 const apply=useCallback(()=>{const value=`${camera.current.x},${camera.current.y},${camera.current.scale}`;if(layer.current)layer.current.style.transform=`translate3d(${camera.current.x}px,${camera.current.y}px,0) scale(${camera.current.scale})`;if(viewport.current)viewport.current.dataset.camera=value},[]);
 const svg=()=>anchor.current?.querySelector<SVGSVGElement>("svg[data-real-to-screen-transform]")||null;
 // Hold the drawing at the reference projection: after a refit, scale/translate the viewer back onto it.
 const sync=useCallback(()=>{
  const node=svg(),current=node&&parseProjection(node);if(!current||!anchor.current)return;
  const ref=reference.current;
  if(resetReference.current||!ref||ref.w!==current.w||ref.h!==current.h){reference.current=current;resetReference.current=false}
  const base=reference.current!,k=base.a/current.a;
  anchor.current.style.transform=`matrix(${k},0,0,${k},${base.e-k*current.e},${base.f-k*current.f})`;
  setProjection(previous=>previous&&previous.a===current.a&&previous.d===current.d&&previous.e===current.e&&previous.f===current.f&&previous.w===current.w&&previous.h===current.h?previous:current);
 },[]);
 const fit=()=>{camera.current={x:0,y:0,scale:1};apply();resetReference.current=true;sync()},zoom=(factor:number)=>{camera.current.scale=Math.max(.35,Math.min(4,camera.current.scale*factor));apply()};
 useEffect(()=>{camera.current={x:0,y:0,scale:1};apply();resetReference.current=true;setSelectedWire(null);setPreview(undefined);drag.current=undefined},[circuit]);
 useEffect(()=>{const node=viewport.current;if(!node)return;const wheel=(event:WheelEvent)=>{event.preventDefault();event.stopPropagation();zoom(event.deltaY<0?1.12:.89)};node.addEventListener("wheel",wheel,{passive:false,capture:true});return()=>node.removeEventListener("wheel",wheel,{capture:true})},[]);
 useEffect(()=>{const node=anchor.current;if(!node)return;const observer=new MutationObserver(sync);observer.observe(node,{childList:true,subtree:true,attributes:true,attributeFilter:["data-real-to-screen-transform","width","height"]});sync();return()=>observer.disconnect()},[sync]);
 useEffect(()=>{if(selectedWire&&!applied.some(item=>item.type==="schematic_trace"&&item.schematic_trace_id===selectedWire))setSelectedWire(null)},[applied,selectedWire]);

 // Screen → svg user units (inverse screen CTM, which includes the camera zoom and the anchor) → circuit units.
 const matrices=()=>{const node=svg(),r=node&&parseProjection(node),ctm=node?.getScreenCTM();if(!node||!r||!ctm)return;return {toSvg:DOMMatrix.fromMatrix(ctm).inverse(),r}};
 const toCircuit=(x:number,y:number,toSvg:DOMMatrix,r:Projection)=>{const p=new DOMPoint(x,y).matrixTransform(toSvg);return {x:(p.x-r.e)/r.a,y:(p.y-r.f)/r.d}};
 const circuitDelta=(d:{x:number;y:number;toSvg:DOMMatrix;r:Projection},x:number,y:number)=>{const a=toCircuit(d.x,d.y,d.toSvg,d.r),b=toCircuit(x,y,d.toSvg,d.r);return {dx:b.x-a.x,dy:b.y-a.y}};
 const traceAt=(x:number,y:number)=>{
  const m=matrices();if(!m)return null;const p=toCircuit(x,y,m.toSvg,m.r);
  // Circuit units per screen pixel = (svg units per pixel) / (svg units per circuit unit).
  const tolerance=WIRE_HIT_PX*Math.hypot(m.toSvg.a,m.toSvg.b)/Math.abs(m.r.a);
  let best:{id:string;distance:number}|null=null;
  for(const item of applied)if(item.type==="schematic_trace")for(const edge of item.edges||[]){const distance=segmentDistance(p,edge.from,edge.to);if(distance<=tolerance&&(!best||distance<best.distance))best={id:item.schematic_trace_id,distance}}
  return best?.id??null;
 };
 const startPan=(e:React.PointerEvent)=>{drag.current={kind:"pan",x:e.clientX,y:e.clientY,cx:camera.current.x,cy:camera.current.y}};
 const onPointerDown=(e:React.PointerEvent<HTMLDivElement>)=>{
  const target=e.target as Element;
  if(target.closest?.(".schematic-nets,.wiring-toolbar,.schematic-controls"))return;
  viewport.current?.focus({preventScroll:true});
  const panning=mode==="pan"||spaceHeld||e.button===1;
  const handle=target.closest?.("[data-bend-handle]") as HTMLElement|null;
  const m=panning?undefined:matrices();
  if(handle&&m){
   drag.current={kind:"bend",wire:handle.dataset.wire!,index:Number(handle.dataset.segment),horizontal:handle.dataset.orientation==="horizontal",x:e.clientX,y:e.clientY,...m,moved:false,delta:0};
  }else if(!panning){
   const component=target.closest?.("[data-schematic-component-id]")?.getAttribute("data-schematic-component-id"),id=component?mapping[component]:undefined;
   const trace=!component?(target.closest?.("[data-schematic-trace-id]")?.getAttribute("data-schematic-trace-id")??traceAt(e.clientX,e.clientY)):null;
   if(id){onSelect(id);setSelectedWire(null);if(m)drag.current={kind:"part",id,x:e.clientX,y:e.clientY,...m,moved:false,dx:0,dy:0}}
   else if(trace){setSelectedWire(trace);e.stopPropagation();return}
   else{setSelectedWire(null);startPan(e)}
  }else startPan(e);
  if(drag.current)(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  e.stopPropagation();
 };
 const onPointerMove=(e:React.PointerEvent<HTMLDivElement>)=>{
  const d=drag.current;if(!d)return;e.stopPropagation();
  if(d.kind==="pan"){camera.current.x=d.cx+e.clientX-d.x;camera.current.y=d.cy+e.clientY-d.y;apply();return}
  if(!d.moved&&Math.hypot(e.clientX-d.x,e.clientY-d.y)<START_PX)return;
  d.moved=true;
  const {dx,dy}=circuitDelta(d,e.clientX,e.clientY),base={layout,past:[],future:[]};
  if(d.kind==="part"){const sx=snap(dx),sy=snap(dy);if(sx===d.dx&&sy===d.dy)return;d.dx=sx;d.dy=sy;setPreview(layoutReducer(base,{type:"move",id:d.id,dx:sx,dy:sy}).layout)}
  else{const delta=snap(d.horizontal?dy:dx);if(delta===d.delta)return;d.delta=delta;setPreview(layoutReducer(base,{type:"bend",wire:d.wire,index:d.index,delta}).layout)}
 };
 const onPointerUp=(e:React.PointerEvent<HTMLDivElement>)=>{
  const d=drag.current;drag.current=undefined;
  if((e.currentTarget as HTMLElement).hasPointerCapture?.(e.pointerId))(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  if(!d)return;e.stopPropagation();
  if(d.kind==="part"&&d.moved)dispatch({type:"move",id:d.id,dx:d.dx,dy:d.dy});
  if(d.kind==="bend"&&d.moved)dispatch({type:"bend",wire:d.wire,index:d.index,delta:d.delta});
  setPreview(undefined);
 };
 const partIds=useMemo(()=>new Set(Object.values(mapping)),[mapping]);
 const onKeyDown=(e:React.KeyboardEvent<HTMLDivElement>)=>{
  const key=e.key.toLowerCase(),mod=e.ctrlKey||e.metaKey;
  if(mod&&(key==="z"||key==="y")){e.preventDefault();e.stopPropagation();dispatch({type:key==="y"||e.shiftKey?"redo":"undo"});return}
  if(e.target!==viewport.current)return;
  if(key===" "){e.preventDefault();setSpaceHeld(true);return}
  const step=(e.shiftKey?10:1)*SNAP,up=(projection?.d??-1)<0?step:-step;
  const move:Record<string,[number,number]>={arrowleft:[-step,0],arrowright:[step,0],arrowup:[0,up],arrowdown:[0,-up]};
  if(move[key]&&selectedId&&partIds.has(selectedId)){e.preventDefault();dispatch({type:"move",id:selectedId,dx:move[key][0],dy:move[key][1]})}
 };
 const onKeyUp=(e:React.KeyboardEvent)=>{if(e.key===" ")setSpaceHeld(false)};

 const trace=selectedWire?applied.find(item=>item.type==="schematic_trace"&&item.schematic_trace_id===selectedWire):undefined;
 const handles:{index:number;horizontal:boolean;left:number;top:number}[]=trace&&projection?// Original segments only: an unedited trace has no index marks, so its edge order is the segment index.
(trace.edges||[]).map((edge:any,i:number)=>({edge,index:(trace.edges||[]).some((item:any)=>typeof item.aura_segment_index==="number")?edge.aura_segment_index:i})).filter(({index}:{index:unknown})=>typeof index==="number").map(({edge,index}:{edge:any;index:number})=>{
  const horizontal=Math.abs(edge.from.y-edge.to.y)<=Math.abs(edge.from.x-edge.to.x),x=(edge.from.x+edge.to.x)/2,y=(edge.from.y+edge.to.y)/2;
  return {index,horizontal,left:projection.a*x+projection.e,top:projection.d*y+projection.f};
 }):[];
 const bendKey=(wire:string,handle:{index:number;horizontal:boolean})=>(e:React.KeyboardEvent)=>{
  const key=e.key.toLowerCase(),up=(projection?.d??-1)<0?SNAP:-SNAP;
  const delta=handle.horizontal?{arrowup:up,arrowdown:-up}[key]:{arrowleft:-SNAP,arrowright:SNAP}[key];
  if(delta===undefined)return;e.preventDefault();e.stopPropagation();dispatch({type:"bend",wire,index:handle.index,delta:delta*(e.shiftKey?10:1)});
 };
 // The viewer pans itself on mouse events; all camera and edit gestures are handled here instead.
 const swallow=(e:React.MouseEvent)=>{if(!(e.target as Element).closest?.(".schematic-nets,.wiring-toolbar,.schematic-controls,.bend-handle"))e.stopPropagation()};
 const panning=mode==="pan"||spaceHeld;
 const netList=nets.length?nets:[...new Map(circuit.filter((item:any)=>item.type==="aura_electrical_connection"&&item.netId).map((item:any)=>[item.netId,item])).values()];
 return <div ref={viewport} className="schematic-camera" data-testid="schematic-camera" data-camera="0,0,1" data-mode={panning?"pan":"select"} tabIndex={0} role="application" aria-label="Wiring view. Drag parts or wire handles to rearrange; Ctrl+Z undo, Ctrl+Shift+Z redo; hold Space to pan."
  onPointerDownCapture={onPointerDown} onPointerMoveCapture={onPointerMove} onPointerUpCapture={onPointerUp} onPointerCancelCapture={onPointerUp} onMouseDownCapture={swallow} onMouseMoveCapture={swallow} onMouseUpCapture={swallow} onKeyDown={onKeyDown} onKeyUp={onKeyUp} onBlur={()=>setSpaceHeld(false)}>
   <div className="schematic-layer" ref={layer}><div className="schematic-anchor" ref={anchor}>
    <Suspense fallback={<div className="schematic-loading" role="status">Loading schematic…</div>}><SchematicViewer circuitJson={applied as never} editingEnabled={false} clickToInteractEnabled={false} containerStyle={{height:"100%"}}/></Suspense>
    {selectedWire&&<style>{`.schematic-anchor [data-schematic-trace-id="${CSS.escape(selectedWire)}"] path{stroke:var(--accent,#6f8f7a)!important;stroke-width:3px}`}</style>}
    {trace&&wireIds[trace.schematic_trace_id]&&<div className="bend-handles" data-testid="bend-handles">{handles.map(handle=><button key={handle.index} type="button" className="bend-handle" data-testid="bend-handle" data-bend-handle="" data-wire={wireIds[trace.schematic_trace_id]} data-segment={handle.index} data-orientation={handle.horizontal?"horizontal":"vertical"}
     style={{left:handle.left,top:handle.top,cursor:handle.horizontal?"ns-resize":"ew-resize"}} aria-label={`Bend segment ${handle.index+1} of wire ${wireIds[trace.schematic_trace_id]}`} onKeyDown={bendKey(wireIds[trace.schematic_trace_id],handle)}/>)}</div>}
   </div></div>
   <div className="wiring-toolbar" role="toolbar" aria-label="Wiring tools">
    <button type="button" aria-pressed={mode==="select"} onClick={()=>setMode("select")} title="Select and drag parts or wires">Select</button>
    <button type="button" aria-pressed={mode==="pan"} onClick={()=>setMode("pan")} title="Drag to pan (or hold Space)">Pan</button>
    <span className="wiring-toolbar-sep" aria-hidden="true"/>
    <button type="button" disabled={!canUndo} aria-keyshortcuts="Control+Z" onClick={()=>dispatch({type:"undo"})} title="Undo wiring edit (Ctrl+Z)">Undo</button>
    <button type="button" disabled={!canRedo} aria-keyshortcuts="Control+Shift+Z Control+Y" onClick={()=>dispatch({type:"redo"})} title="Redo wiring edit (Ctrl+Shift+Z)">Redo</button>
   </div>
   <div className="schematic-nets" data-testid="schematic-nets">{netList.map((net:any)=><button key={net.netId} data-net-id={net.netId} className={selectedNet===net.netId?"active":""} style={{borderColor:net.displayStyle?.color}} onClick={e=>{e.stopPropagation();if(onSelectNet)onSelectNet(net.netId);else onSelect(`net:${net.netId}`)}}>{layout.labels[net.netId]||net.role?.replaceAll("-"," ")||net.netId}</button>)}</div>
   <div className="schematic-controls"><button onClick={fit}>FIT</button><button onClick={()=>zoom(1.2)}>+</button><button onClick={()=>zoom(.8)}>−</button><button onClick={fit}>RESET</button></div>
  </div>;
}

// Inspector field for a component or net display name. Enter or leaving the field commits; Escape reverts; an empty
// value (or the generated name) clears the override.
export function DisplayNameField({value,original,onCommit}:{value:string;original:string;onCommit:(label:string)=>void}){
 const [draft,setDraft]=useState(value||original);
 useEffect(()=>setDraft(value||original),[value,original]);
 const commit=()=>{const next=draft.trim();onCommit(next===original?"":next);if(!next)setDraft(original)};
 return <label className="display-name"><span>Display name</span><input value={draft} placeholder={original} onChange={e=>setDraft(e.target.value)} onBlur={commit}
  onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();commit()}if(e.key==="Escape"){e.preventDefault();e.stopPropagation();setDraft(value||original)}}}/></label>;
}
