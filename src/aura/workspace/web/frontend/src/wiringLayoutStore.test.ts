import {describe,expect,it} from "vitest";
import {normalizeLayout} from "./wiringLayoutStore";

describe("normalizeLayout",()=>{
 it("keeps well-formed entries",()=>{
  const layout={parts:{a:{dx:1,dy:-2.5}},wires:{w:[1,-3]},labels:{a:"Brain"}};
  expect(normalizeLayout(layout)).toEqual(layout);
 });
 it("drops values that would crash a React render or break the geometry",()=>{
  const hostile={
   labels:{ok:"fine",obj:{x:1},num:3,long:"x".repeat(201),nul:null},
   parts:{ok:{dx:1,dy:2},xy:{x:1,y:2},str:{dx:"1",dy:2},inf:{dx:Infinity,dy:0},nan:{dx:NaN,dy:0},arr:[1,2],nul:null},
   wires:{ok:[1,2],obj:{bends:[3]},str:"no",mixed:[1,"2"],inf:[1,Infinity],tooMany:Array.from({length:65},(_,i)=>i)},
  };
  expect(normalizeLayout(hostile)).toEqual({labels:{ok:"fine"},parts:{ok:{dx:1,dy:2}},wires:{ok:[1,2]}});
 });
 it("tolerates non-object input",()=>{
  for(const raw of [undefined,null,3,"x",[],{parts:[],wires:"x",labels:3}])expect(normalizeLayout(raw)).toEqual({parts:{},wires:{},labels:{}});
 });
});
