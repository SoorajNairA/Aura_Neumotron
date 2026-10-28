import {KeyboardEvent,RefObject,useEffect,useMemo,useRef,useState} from "react";
import type {Menu} from "./MenuBar";

export const SHARE_DISABLED_REASON="Sharing needs a hosted server with access control; not available in this build";

type FileMenuActions={onNew:()=>void;onOpen:()=>void;onSave:()=>void;onCopy:()=>void;onExport:()=>void;onImport:()=>void;onLocalCopy:()=>void};

// File menu: plain rows, shortcut hints right-aligned, rules before Export and Import, ▸ for submenus.
export function fileMenu(a:FileMenuActions):Menu{
 return {label:"File",items:[
  {label:"New",onSelect:a.onNew},
  {label:"Open",shortcut:"Ctrl+O",onSelect:a.onOpen},
  {label:"Save",shortcut:"Ctrl+S",onSelect:a.onSave},
  {label:"Make a copy",onSelect:a.onCopy},
  {label:"Export",separatorBefore:true,items:[{label:"Project ZIP",onSelect:a.onExport},{label:"Shareable link",disabled:true,title:SHARE_DISABLED_REASON,onSelect:()=>{}}]},
  {label:"Import",separatorBefore:true,items:[{label:"Project ZIP…",onSelect:a.onImport}]},
  {label:"Save local copy",onSelect:a.onLocalCopy},
 ]};
}

const FOCUSABLE="button:not(:disabled),input:not(:disabled),[href],[tabindex]:not([tabindex='-1'])";

// Modal behaviour shared by the dialogs: Escape closes, Tab stays inside, focus goes back to where it was.
function useModal(ref:RefObject<HTMLElement>,onClose:()=>void){
 const close=useRef(onClose);close.current=onClose;
 useEffect(()=>{
  const previous=document.activeElement as HTMLElement|null;
  return()=>{if(previous&&previous.isConnected&&previous!==document.body)previous.focus();else requestAnimationFrame(()=>{const trigger=document.querySelector<HTMLElement>('[data-menu="File"] > button');if(document.activeElement===document.body)trigger?.focus()})};
 },[]);
 return (event:KeyboardEvent<HTMLElement>)=>{
  if(event.key==="Escape"){event.preventDefault();event.stopPropagation();close.current()}
  else if(event.key==="Tab"&&ref.current){
   const nodes=[...ref.current.querySelectorAll<HTMLElement>(FOCUSABLE)];if(!nodes.length)return;
   const first=nodes[0],last=nodes[nodes.length-1];
   if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
   else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
  }
 };
}

export type ProjectRow={projectId:string;objective?:string;status?:string;revision?:number;updatedAt?:string|null};

const rowTitle=(p:ProjectRow)=>p.objective||p.projectId;
const when=(value?:string|null)=>{if(!value)return "";const d=new Date(value);return Number.isNaN(d.getTime())?"":d.toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"})};

// Ctrl+O dialog: search box focused on open, list reachable with the arrow keys, last row creates a new project.
export function OpenDialog({apiBase,initial,currentId,onOpen,onNew,onClose}:{apiBase:string;initial:ProjectRow[];currentId:string|null;onOpen:(id:string)=>void;onNew:()=>void;onClose:()=>void}){
 const [projects,setProjects]=useState<ProjectRow[]>(initial),[query,setQuery]=useState(""),[failed,setFailed]=useState(false);
 const box=useRef<HTMLElement>(null),search=useRef<HTMLInputElement>(null),keys=useModal(box,onClose);
 useEffect(()=>{search.current?.focus()},[]);
 useEffect(()=>{let live=true;fetch(`${apiBase}/api/projects`).then(r=>r.ok?r.json():Promise.reject(r.status)).then(list=>{if(live&&Array.isArray(list))setProjects(list)}).catch(()=>{if(live)setFailed(true)});return()=>{live=false}},[apiBase]);
 const shown=useMemo(()=>{const q=query.trim().toLowerCase();return q?projects.filter(p=>`${rowTitle(p)} ${p.projectId} ${p.status||""}`.toLowerCase().includes(q)):projects},[projects,query]);
 const move=(event:KeyboardEvent<HTMLElement>)=>{
  if(event.key!=="ArrowDown"&&event.key!=="ArrowUp")return;
  const rows=[...box.current!.querySelectorAll<HTMLButtonElement>(".open-row")],at=rows.indexOf(document.activeElement as HTMLButtonElement);
  event.preventDefault();
  if(event.key==="ArrowDown")rows[at+1]?.focus();
  else if(at<=0)search.current?.focus();else rows[at-1].focus();
 };
 return <div className="dialog-scrim file-scrim" onMouseDown={event=>{if(event.target===event.currentTarget)onClose()}}>
  <section ref={box} className="file-dialog open-dialog" role="dialog" aria-modal="true" aria-label="Open project" onKeyDown={event=>{keys(event);if(!event.defaultPrevented)move(event)}}>
   <h2>Open project</h2>
   <input ref={search} type="search" aria-label="Search projects" placeholder="Search projects" value={query} onChange={event=>setQuery(event.target.value)}/>
   <div className="open-list">
    {shown.map(p=><button key={p.projectId} className="open-row" aria-current={p.projectId===currentId?"true":undefined} onClick={()=>p.projectId===currentId?onClose():onOpen(p.projectId)}>
     <b>{rowTitle(p)}</b><span>{p.projectId===currentId?"Current · ":""}{p.revision!==undefined?`REV ${String(p.revision).padStart(2,"0")}`:""}{when(p.updatedAt)?` · ${when(p.updatedAt)}`:""}</span>
    </button>)}
    {!shown.length&&<p className="open-empty">{failed&&!projects.length?"Saved projects could not be loaded.":query?"No matching projects.":"No saved projects yet."}</p>}
   </div>
   <button className="open-row open-new" onClick={onNew}><b>Create new project</b><span>Start from an idea</span></button>
  </section>
 </div>;
}

// Shown before New / Open / Import / Make a copy when the wiring layout has edits that were not saved.
export function UnsavedDialog({busy,onSave,onDiscard,onCancel}:{busy:boolean;onSave:()=>void;onDiscard:()=>void;onCancel:()=>void}){
 const box=useRef<HTMLElement>(null),keys=useModal(box,onCancel),save=useRef<HTMLButtonElement>(null);
 useEffect(()=>{save.current?.focus()},[]);
 return <div className="dialog-scrim file-scrim">
  <section ref={box} className="file-dialog unsaved-dialog" role="dialog" aria-modal="true" aria-label="Unsaved changes" aria-describedby="unsaved-body" onKeyDown={keys}>
   <h2>Unsaved changes</h2>
   <p id="unsaved-body">Your wiring layout has changes that are not saved yet.</p>
   <div className="preview-actions"><button onClick={onCancel}>Cancel</button><button onClick={onDiscard} disabled={busy}>Discard</button><button ref={save} className="primary" onClick={onSave} disabled={busy}>Save</button></div>
  </section>
 </div>;
}
