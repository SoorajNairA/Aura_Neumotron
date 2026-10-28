import {useEffect,useRef,useState} from "react";

export type FabAction={label:string;icon:string;onClick:()=>void;pressed?:boolean};

// Round button in the viewport's top-right corner; expands its actions leftward. Collapses on a second click,
// an outside click or Escape (focus returns to the button).
export function ViewFab({actions}:{actions:FabAction[]}){
 const [open,setOpen]=useState(false),root=useRef<HTMLDivElement>(null),button=useRef<HTMLButtonElement>(null);
 useEffect(()=>{if(!open)return;
  const away=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false)};
  const escape=(event:KeyboardEvent)=>{if(event.key==="Escape"){setOpen(false);button.current?.focus()}};
  document.addEventListener("pointerdown",away);document.addEventListener("keydown",escape);
  return()=>{document.removeEventListener("pointerdown",away);document.removeEventListener("keydown",escape)}},[open]);
 return <div ref={root} className={`view-fab${open?" open":""}`}>
  <button ref={button} className="fab" aria-label="View controls" aria-expanded={open} onClick={()=>setOpen(!open)}><span aria-hidden="true">{open?"×":"⋯"}</span></button>
  {open&&<div className="fab-actions" role="group" aria-label="View actions">
   {actions.map(action=><button key={action.label} aria-pressed={action.pressed} onClick={action.onClick}><span className="fab-icon" aria-hidden="true">{action.icon}</span>{action.label}</button>)}
  </div>}
 </div>;
}
