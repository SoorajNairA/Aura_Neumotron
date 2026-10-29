import {useCallback,useEffect,useRef,useState} from "react";
import {emptyLayout,layoutReducer,type LayoutAction,type LayoutHistory,type WiringLayout} from "./wiringLayout";

// Saved wiring-editor layout (part offsets, wire bends, display names), stored server-side per project.
export type {WiringLayout} from "./wiringLayout";
export {emptyLayout} from "./wiringLayout";
export const AUTOSAVE_MS=1000;

const record=(value:any)=>value&&typeof value==="object"&&!Array.isArray(value)?value:{};
const normalize=(raw:any):WiringLayout=>({parts:record(raw?.parts),wires:record(raw?.wires),labels:record(raw?.labels)});

// GET the layout when the project loads (empty when none or 404); `setLayout` marks it dirty; `flush()` PUTs it and clears dirty.
// `dispatch` applies a wiring-view edit (with undo/redo history) and autosaves AUTOSAVE_MS after the last edit.
// `setLayout` alone does not autosave. `flush` resolves true on success (or when there is nothing loaded to write), false on failure.
// Writing is refused until the first GET finished, so a slow load can never overwrite a saved layout with an empty one.
export function useWiringLayout(projectId:string|null,apiBase=""){
 const [layout,setLayoutState]=useState<WiringLayout>(emptyLayout),[dirty,setDirty]=useState(false),[loaded,setLoaded]=useState(false);
 const [history,setHistory]=useState({undo:0,redo:0});
 const latest=useRef(layout),version=useRef(0),loadedRef=useRef(false),active=useRef(projectId);
 const stacks=useRef<{past:WiringLayout[];future:WiringLayout[]}>({past:[],future:[]}),timer=useRef<ReturnType<typeof setTimeout>>();
 const cancelAutosave=()=>{if(timer.current){clearTimeout(timer.current);timer.current=undefined}};
 const resetHistory=()=>{stacks.current={past:[],future:[]};setHistory({undo:0,redo:0})};
 useEffect(()=>{
  cancelAutosave();resetHistory();
  active.current=projectId;loadedRef.current=false;setLoaded(false);version.current=0;latest.current=emptyLayout();setLayoutState(latest.current);setDirty(false);
  if(!projectId)return;
  const id=projectId;let live=true;
  fetch(`${apiBase}/api/projects/${id}/layout`).then(async response=>{
   if(!live)return;
   if(response.status===404){loadedRef.current=true;setLoaded(true);return}
   if(!response.ok)return;
   const body=await response.json().catch(()=>undefined);
   if(!live)return;
   loadedRef.current=true;setLoaded(true);
   // Edits made before the load finished win over the stored copy.
   if(version.current===0){latest.current=normalize(body?.layout);setLayoutState(latest.current)}
  }).catch(()=>undefined);
  return()=>{live=false;cancelAutosave()};
 },[projectId,apiBase]);
 const setLayout=useCallback((next:WiringLayout|((current:WiringLayout)=>WiringLayout))=>{
  const value=typeof next==="function"?next(latest.current):next;
  latest.current=normalize(value);version.current+=1;setLayoutState(latest.current);setDirty(true);
 },[]);
 const flush=useCallback(async():Promise<boolean>=>{
  cancelAutosave();
  const id=active.current;
  if(!id||!loadedRef.current)return !id;
  const sent=version.current,body=JSON.stringify({layout:latest.current});
  try{
   const response=await fetch(`${apiBase}/api/projects/${id}/layout`,{method:"PUT",headers:{"content-type":"application/json"},body});
   if(!response.ok)return false;
   if(active.current===id){if(version.current===sent)setDirty(false)}
   return true;
  }catch{return false}
 },[apiBase]);
 const flushRef=useRef(flush);flushRef.current=flush;
 const dispatch=useCallback((action:LayoutAction)=>{
  const before:LayoutHistory={layout:latest.current,...stacks.current};
  const after=layoutReducer(before,action);
  if(after===before)return;
  stacks.current={past:after.past,future:after.future};setHistory({undo:after.past.length,redo:after.future.length});
  if(after.layout===latest.current)return;
  setLayout(after.layout);
  cancelAutosave();
  const id=active.current;
  // Waits for the first GET (flush refuses before it), then saves.
  const save=()=>{timer.current=undefined;if(active.current!==id)return;if(!loadedRef.current){timer.current=setTimeout(save,AUTOSAVE_MS);return}void flushRef.current()};
  timer.current=setTimeout(save,AUTOSAVE_MS);
 },[setLayout]);
 return {layout,setLayout,dirty,flush,loaded,dispatch,canUndo:history.undo>0,canRedo:history.redo>0};
}
