import {useCallback,useEffect,useRef,useState} from "react";

// Saved wiring-editor layout (offsets, bends, label positions), stored server-side per project.
export type WiringLayout={parts:Record<string,any>;wires:Record<string,any>;labels:Record<string,any>};
export const emptyLayout=():WiringLayout=>({parts:{},wires:{},labels:{}});

const normalize=(raw:any):WiringLayout=>({parts:raw?.parts&&typeof raw.parts==="object"?raw.parts:{},wires:raw?.wires&&typeof raw.wires==="object"?raw.wires:{},labels:raw?.labels&&typeof raw.labels==="object"?raw.labels:{}});

// GET the layout when the project loads (empty when none or 404); `setLayout` marks it dirty; `flush()` PUTs it and clears dirty.
// There is no autosave here. `flush` resolves true on success (or when there is nothing loaded to write), false on failure.
// Writing is refused until the first GET finished, so a slow load can never overwrite a saved layout with an empty one.
export function useWiringLayout(projectId:string|null,apiBase=""){
 const [layout,setLayoutState]=useState<WiringLayout>(emptyLayout),[dirty,setDirty]=useState(false);
 const latest=useRef(layout),version=useRef(0),loaded=useRef(false),active=useRef(projectId);
 useEffect(()=>{
  active.current=projectId;loaded.current=false;version.current=0;latest.current=emptyLayout();setLayoutState(latest.current);setDirty(false);
  if(!projectId)return;
  const id=projectId;let live=true;
  fetch(`${apiBase}/api/projects/${id}/layout`).then(async response=>{
   if(!live)return;
   if(response.status===404){loaded.current=true;return}
   if(!response.ok)return;
   const body=await response.json().catch(()=>undefined);
   if(!live)return;
   loaded.current=true;
   // Edits made before the load finished win over the stored copy.
   if(version.current===0){latest.current=normalize(body?.layout);setLayoutState(latest.current)}
  }).catch(()=>undefined);
  return()=>{live=false};
 },[projectId,apiBase]);
 const setLayout=useCallback((next:WiringLayout|((current:WiringLayout)=>WiringLayout))=>{
  const value=typeof next==="function"?next(latest.current):next;
  latest.current=normalize(value);version.current+=1;setLayoutState(latest.current);setDirty(true);
 },[]);
 const flush=useCallback(async():Promise<boolean>=>{
  const id=active.current;
  if(!id||!loaded.current)return !id;
  const sent=version.current,body=JSON.stringify({layout:latest.current});
  try{
   const response=await fetch(`${apiBase}/api/projects/${id}/layout`,{method:"PUT",headers:{"content-type":"application/json"},body});
   if(!response.ok)return false;
   if(active.current===id){if(version.current===sent)setDirty(false)}
   return true;
  }catch{return false}
 },[apiBase]);
 return {layout,setLayout,dirty,flush};
}
