import {KeyboardEvent,useEffect,useRef,useState} from "react";

export type MenuItem={label:string;hint?:string;disabled?:boolean;onSelect:()=>void};
export type Menu={label:string;items:MenuItem[]};

// Application menu: each menu opens on click or ArrowDown, closes on selection, outside click or Escape
// (focus returns to its trigger); arrow keys move between items.
export function MenuBar({menus}:{menus:Menu[]}){
 const [open,setOpen]=useState<string|null>(null),root=useRef<HTMLElement>(null),triggers=useRef<Record<string,HTMLButtonElement|null>>({});
 const close=(focus=false)=>{const was=open;setOpen(null);if(focus&&was)triggers.current[was]?.focus()};
 useEffect(()=>{if(!open)return;const away=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(null)};
  document.addEventListener("pointerdown",away);return()=>document.removeEventListener("pointerdown",away)},[open]);
 useEffect(()=>{if(open)root.current?.querySelector<HTMLButtonElement>(`[data-menu="${open}"] [role=menuitem]:not(:disabled)`)?.focus()},[open]);
 const keys=(event:KeyboardEvent<HTMLDivElement>)=>{
  const items=[...event.currentTarget.querySelectorAll<HTMLButtonElement>("[role=menuitem]:not(:disabled)")],index=items.indexOf(document.activeElement as HTMLButtonElement);
  if(event.key==="Escape"){event.preventDefault();close(true)}
  else if(event.key==="ArrowDown"||event.key==="ArrowUp"){event.preventDefault();items[(index+(event.key==="ArrowDown"?1:-1)+items.length)%items.length]?.focus()}
 };
 return <nav ref={root} className="app-menu" aria-label="Application menu">
  {menus.map(menu=><div className="app-menu-entry" key={menu.label} data-menu={menu.label}>
   <button ref={node=>{triggers.current[menu.label]=node}} aria-haspopup="menu" aria-expanded={open===menu.label} onClick={()=>setOpen(open===menu.label?null:menu.label)}
    onKeyDown={event=>{if(event.key==="ArrowDown"){event.preventDefault();setOpen(menu.label)}if(event.key==="Escape")close(true)}}>{menu.label}<span className="caret" aria-hidden="true">⌄</span></button>
   {open===menu.label&&<div className="app-menu-popover" role="menu" aria-label={menu.label} onKeyDown={keys}>
    {menu.items.map(item=><button key={item.label} role="menuitem" disabled={item.disabled} onClick={()=>{setOpen(null);item.onSelect();
     // Keep keyboard users in place: if the action moved focus nowhere, return it to this menu's trigger.
     requestAnimationFrame(()=>{if(document.activeElement===document.body)triggers.current[menu.label]?.focus()})}}>{item.label}{item.hint&&<small>{item.hint}</small>}</button>)}
   </div>}
  </div>)}
 </nav>;
}
