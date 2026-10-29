import {describe,expect,it} from "vitest";
import {applyLayout,emptyLayout,layoutReducer,pruneLayout,traceWireIds,type LayoutHistory,type WiringLayout} from "./wiringLayout";

// Two parts joined by one three-segment trace: A port (1,0) → (2,0) → (2,3) → B port (7,3).
const circuit=()=>[
 {type:"source_component",source_component_id:"src_a",name:"U1 Board",display_name:"Board"},
 {type:"source_component",source_component_id:"src_b",name:"M1 Fan",display_name:"Fan"},
 {type:"schematic_component",schematic_component_id:"sch_a",source_component_id:"src_a",center:{x:0,y:0},size:{width:2,height:1},aura_semantic_id:"component-a",symbol_display_value:"Board"},
 {type:"schematic_component",schematic_component_id:"sch_b",source_component_id:"src_b",center:{x:8,y:3},size:{width:2,height:1},aura_semantic_id:"component-b",symbol_display_value:"Fan"},
 {type:"schematic_port",schematic_port_id:"port_a",schematic_component_id:"sch_a",center:{x:1,y:0}},
 {type:"schematic_port",schematic_port_id:"port_b",schematic_component_id:"sch_b",center:{x:7,y:3}},
 {type:"schematic_text",schematic_text_id:"text_a",schematic_component_id:"sch_a",position:{x:-1,y:-.5},text:""},
 {type:"schematic_text",schematic_text_id:"name_a",schematic_component_id:"sch_a",position:{x:-1,y:.6},text:"Board"},
 {type:"schematic_trace",schematic_trace_id:"trace_0",aura_graph_connection_id:"conn-1",edges:[{from:{x:1,y:0},to:{x:2,y:0}},{from:{x:2,y:0},to:{x:2,y:3}},{from:{x:2,y:3},to:{x:7,y:3}}],junctions:[]},
 {type:"aura_electrical_connection",aura_electrical_connection_id:"e0",from:"U1.OUT",to:"M1.IN",netId:"net-1",graphConnectionId:"conn-1"},
];
const mapping={sch_a:"component-a",sch_b:"component-b"};
const layout=(patch:Partial<WiringLayout>):WiringLayout=>({...emptyLayout(),...patch});
const find=(items:any[],type:string,key:string,id:string)=>items.find(item=>item.type===type&&item[key]===id);
const trace=(items:any[])=>find(items,"schematic_trace","schematic_trace_id","trace_0");
const same=(a:any,b:any)=>Math.abs(a.x-b.x)<1e-9&&Math.abs(a.y-b.y)<1e-9;
function expectConnectedOrthogonal(edges:any[]){
 for(const edge of edges)expect(Math.abs(edge.from.x-edge.to.x)<1e-9||Math.abs(edge.from.y-edge.to.y)<1e-9).toBe(true);
 for(let i=1;i<edges.length;i++)expect(same(edges[i-1].to,edges[i].from)).toBe(true);
}

describe("applyLayout",()=>{
 it("move shifts the component, its ports, its texts and the attached trace endpoint by (dx,dy)",()=>{
  const out=applyLayout(circuit(),layout({parts:{"component-a":{dx:1,dy:2}}}),mapping);
  expect(find(out,"schematic_component","schematic_component_id","sch_a").center).toEqual({x:1,y:2});
  expect(find(out,"schematic_port","schematic_port_id","port_a").center).toEqual({x:2,y:2});
  expect(find(out,"schematic_text","schematic_text_id","text_a").position).toEqual({x:0,y:1.5});
  const edges=trace(out).edges;
  expect(same(edges[0].from,{x:2,y:2})).toBe(true);
  expect(same(edges.at(-1).to,{x:7,y:3})).toBe(true);
  expectConnectedOrthogonal(edges);
  // The other part is untouched.
  expect(find(out,"schematic_component","schematic_component_id","sch_b").center).toEqual({x:8,y:3});
 });
 it("bend of segment 1 by +2 moves that segment and keeps the trace connected and orthogonal",()=>{
  const out=applyLayout(circuit(),layout({wires:{"conn-1":[0,2]}}),mapping);
  const edges=trace(out).edges;
  expectConnectedOrthogonal(edges);
  const bent=edges.find((edge:any)=>edge.aura_segment_index===1);
  expect(bent.from.x).toBeCloseTo(4);expect(bent.to.x).toBeCloseTo(4);
  // The ends stay on their ports.
  expect(same(edges[0].from,{x:1,y:0})).toBe(true);expect(same(edges.at(-1).to,{x:7,y:3})).toBe(true);
 });
 it("bending an end segment adds a connector instead of moving the port end",()=>{
  const out=applyLayout(circuit(),layout({wires:{"conn-1":[1.5]}}),mapping);
  const edges=trace(out).edges;
  expectConnectedOrthogonal(edges);
  expect(same(edges[0].from,{x:1,y:0})).toBe(true);
  const bent=edges.find((edge:any)=>edge.aura_segment_index===0);
  expect(bent.from.y).toBeCloseTo(1.5);expect(bent.to.y).toBeCloseTo(1.5);
 });
 it("moving both parts of a straight trace keeps it connected and orthogonal",()=>{
  const items=circuit();trace(items).edges=[{from:{x:1,y:0},to:{x:7,y:0}}];find(items,"schematic_port","schematic_port_id","port_b").center={x:7,y:0};
  const out=applyLayout(items,layout({parts:{"component-a":{dx:0,dy:1},"component-b":{dx:1,dy:-2}}}),mapping);
  const edges=trace(out).edges;
  expectConnectedOrthogonal(edges);
  expect(same(edges[0].from,{x:1,y:1})).toBe(true);expect(same(edges.at(-1).to,{x:8,y:-2})).toBe(true);
 });
 it("rename sets the component display name only; ids and pins are unchanged",()=>{
  const before=circuit(),out=applyLayout(before,layout({labels:{"component-a":"Main board"}}),mapping);
  const component=find(out,"schematic_component","schematic_component_id","sch_a"),source=find(out,"source_component","source_component_id","src_a");
  expect(source.display_name).toBe("Main board");expect(component.symbol_display_value).toBe("Main board");
  expect(source.name).toBe("U1 Board");
  // Box parts draw their name as a schematic_text; only that text changes.
  expect(find(out,"schematic_text","schematic_text_id","name_a").text).toBe("Main board");
  expect(find(out,"schematic_text","schematic_text_id","text_a").text).toBe("");
  expect(out.map(item=>item.schematic_component_id??item.source_component_id??item.schematic_port_id)).toEqual(before.map(item=>item.schematic_component_id??item.source_component_id??item.schematic_port_id));
  expect(find(out,"schematic_port","schematic_port_id","port_a")).toEqual(find(before,"schematic_port","schematic_port_id","port_a"));
  expect(find(out,"source_component","source_component_id","src_b").display_name).toBe("Fan");
 });
 it("never mutates the input and changes the render key when the layout changes",()=>{
  const input=circuit(),snapshot=JSON.stringify(input);
  const a=applyLayout(input,layout({parts:{"component-a":{dx:1,dy:0}}}),mapping),b=applyLayout(input,layout({parts:{"component-a":{dx:2,dy:0}}}),mapping);
  expect(JSON.stringify(input)).toBe(snapshot);
  expect((a as any).editCount).not.toBe((b as any).editCount);
  expect((a as any).editCount).not.toBe(0);
 });
 it("ignores entries without numeric offsets and unknown ids",()=>{
  const out=applyLayout(circuit(),layout({parts:{"component-a":{x:12,y:6} as any,"component-gone":{dx:5,dy:5}},wires:{"wire-gone":[3]}}),mapping);
  expect(find(out,"schematic_component","schematic_component_id","sch_a").center).toEqual({x:0,y:0});
 });
});

describe("traceWireIds",()=>{
 it("uses the graph connection id, disambiguated by pins when several traces share it",()=>{
  const items=[...circuit(),{type:"schematic_trace",schematic_trace_id:"trace_1",aura_graph_connection_id:"conn-2",aura_connection:{from:"U1.GND",to:"Q1.GND"},edges:[]},{type:"schematic_trace",schematic_trace_id:"trace_2",aura_graph_connection_id:"conn-2",aura_connection:{from:"U1.GND",to:"M1.GND"},edges:[]},{type:"schematic_trace",schematic_trace_id:"trace_3",edges:[]}];
  expect(traceWireIds(items)).toEqual({trace_0:"conn-1",trace_1:"conn-2:U1.GND>Q1.GND",trace_2:"conn-2:U1.GND>M1.GND",trace_3:"trace_3"});
 });
});

describe("layoutReducer",()=>{
 const start=():LayoutHistory=>({layout:emptyLayout(),past:[],future:[]});
 it("move and bend accumulate; rename sets and clears a label",()=>{
  let state=layoutReducer(start(),{type:"move",id:"component-a",dx:1,dy:2});
  state=layoutReducer(state,{type:"move",id:"component-a",dx:.5,dy:-1});
  expect(state.layout.parts["component-a"]).toEqual({dx:1.5,dy:1});
  state=layoutReducer(state,{type:"bend",wire:"conn-1",index:2,delta:1});
  state=layoutReducer(state,{type:"bend",wire:"conn-1",index:2,delta:.5});
  expect(state.layout.wires["conn-1"]).toEqual([0,0,1.5]);
  state=layoutReducer(state,{type:"rename",id:"component-a",label:"  Main board "});
  expect(state.layout.labels["component-a"]).toBe("Main board");
  state=layoutReducer(state,{type:"rename",id:"component-a",label:""});
  expect(state.layout.labels).toEqual({});
 });
 it("undo and redo walk the edits in order and a new edit clears redo",()=>{
  let state=start();
  state=layoutReducer(state,{type:"move",id:"component-a",dx:1,dy:0});
  state=layoutReducer(state,{type:"bend",wire:"conn-1",index:0,delta:2});
  state=layoutReducer(state,{type:"rename",id:"component-a",label:"Main"});
  state=layoutReducer(state,{type:"undo"});
  expect(state.layout.labels).toEqual({});expect(state.layout.wires["conn-1"]).toEqual([2]);
  state=layoutReducer(state,{type:"undo"});
  expect(state.layout.wires).toEqual({});expect(state.layout.parts["component-a"]).toEqual({dx:1,dy:0});
  state=layoutReducer(state,{type:"redo"});
  expect(state.layout.wires["conn-1"]).toEqual([2]);
  expect(state.future).toHaveLength(1);
  state=layoutReducer(state,{type:"move",id:"component-b",dx:0,dy:1});
  expect(state.future).toHaveLength(0);
  expect(layoutReducer(state,{type:"redo"})).toBe(state);
  expect(layoutReducer(start(),{type:"undo"}).layout).toEqual(emptyLayout());
 });
 it("load replaces the layout and clears history; zero edits are no-ops",()=>{
  let state=layoutReducer(start(),{type:"move",id:"component-a",dx:1,dy:0});
  const loaded=layout({labels:{"component-b":"Fan"}});
  state=layoutReducer(state,{type:"load",layout:loaded});
  expect(state).toEqual({layout:loaded,past:[],future:[]});
  expect(layoutReducer(state,{type:"move",id:"component-a",dx:0,dy:0})).toBe(state);
  expect(layoutReducer(state,{type:"rename",id:"component-b",label:"Fan"})).toBe(state);
 });
 it("prune drops unknown ids from the layout and its history",()=>{
  let state=layoutReducer(start(),{type:"move",id:"component-gone",dx:1,dy:0});
  state=layoutReducer(state,{type:"move",id:"component-a",dx:1,dy:0});
  state=layoutReducer(state,{type:"prune",partIds:new Set(["component-a"]),wireIds:new Set()});
  expect(state.layout.parts).toEqual({"component-a":{dx:1,dy:0}});
  expect(state.past.every(entry=>!("component-gone" in entry.parts))).toBe(true);
  // Nothing left to drop: the same state comes back, so nothing is marked unsaved.
  expect(layoutReducer(state,{type:"prune",partIds:new Set(["component-a"]),wireIds:new Set()})).toBe(state);
 });
});

describe("pruneLayout",()=>{
 it("drops parts, wires and labels whose ids are gone and keeps the rest",()=>{
  const value=layout({parts:{"component-a":{dx:1,dy:1},"component-gone":{dx:2,dy:2}},wires:{"conn-1":[1],"conn-gone":[2]},labels:{"component-a":"A","component-gone":"G","net-1":"Signal"}});
  expect(pruneLayout(value,new Set(["component-a","net-1"]),new Set(["conn-1"]))).toEqual(layout({parts:{"component-a":{dx:1,dy:1}},wires:{"conn-1":[1]},labels:{"component-a":"A","net-1":"Signal"}}));
 });
});

describe("applyLayout on a generated fan schematic",()=>{
 it("keeps every trace orthogonal and connected after moving every part and bending every segment",async()=>{
  const real:any[]=(await import("../e2e/wiringCircuit.json")).default as any;
  const map=Object.fromEntries(real.filter(item=>item.type==="schematic_component").map(item=>[item.schematic_component_id,item.aura_semantic_id]));
  const ids=traceWireIds(real),parts:Record<string,any>={},wires:Record<string,number[]>={};
  Object.values(map).forEach((id,i)=>parts[id as string]={dx:1.3*(i%2?1:-1),dy:-.7*i});
  for(const trace of real.filter(item=>item.type==="schematic_trace"))wires[ids[trace.schematic_trace_id]]=trace.edges.map((_:any,i:number)=>i%2?.4:-.3);
  const out=applyLayout(real,layout({parts,wires}),map);
  for(const trace of out.filter(item=>item.type==="schematic_trace")){
   expectConnectedOrthogonal(trace.edges);
   const original=real.find(item=>item.schematic_trace_id===trace.schematic_trace_id).edges.length;
   expect(trace.edges.filter((edge:any)=>edge.aura_segment_index!==undefined).map((edge:any)=>edge.aura_segment_index)).toEqual([...Array(original).keys()]);
  }
  // Each trace end still sits on a port of the (moved) component.
  const ports=out.filter(item=>item.type==="schematic_port");
  for(const trace of out.filter(item=>item.type==="schematic_trace"))for(const end of [trace.edges[0].from,trace.edges.at(-1).to]){
   const junction=(real.find(item=>item.schematic_trace_id===trace.schematic_trace_id).junctions||[]).some((j:any)=>same(j,end));
   expect(junction||ports.some(port=>same(port.center,end))).toBe(true);
  }
 });
});
