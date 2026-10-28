import {KeyboardEvent,useEffect,useId,useRef,useState} from "react";

// `shortcut` is a right-aligned hint (the key binding itself lives in the app); `separatorBefore` draws a rule above the row;
// `unavailable` keeps the row focusable but inert (aria-disabled) and shows the reason as visible, described text;
// `items` turns the row into a submenu (opens on hover, click or ArrowRight; closes on ArrowLeft or Escape); `title` is a tooltip.
export type MenuItem={label:string;hint?:string;shortcut?:string;title?:string;separatorBefore?:boolean;disabled?:boolean;checked?:boolean;items?:MenuItem[];unavailable?:string;onSelect?:()=>void};
export type Menu={label:string;items:MenuItem[];ariaLabel?:string};

const ownItems=(list:HTMLElement)=>[...list.querySelectorAll<HTMLButtonElement>("[role^=menuitem]:not(:disabled)")].filter(node=>node.closest("[role=menu]")===list);

function aria(shortcut?:string){return shortcut?shortcut.replace(/Ctrl/,"Control"):undefined}

function MenuRow({item,pick}:{item:MenuItem;pick:(item:MenuItem)=>void}){
 const uid=useId(),[sub,setSub]=useState(false),wrap=useRef<HTMLDivElement>(null),button=useRef<HTMLButtonElement>(null),focusChild=useRef(false);
 useEffect(()=>{if(sub&&focusChild.current){focusChild.current=false;const list=wrap.current?.querySelector<HTMLElement>(":scope > [role=menu]");if(list)ownItems(list)[0]?.focus()}},[sub]);
 const content=<><span className="mi-label">{item.label}</span>{item.hint&&<small className="mi-hint">{item.hint}</small>}{item.shortcut&&<kbd className="mi-shortcut" aria-hidden="true">{item.shortcut}</kbd>}{item.items&&<span className="mi-caret" aria-hidden="true">▸</span>}</>;
 const separator=item.separatorBefore?<div role="separator" className="menu-sep"/>:null;
 if(item.unavailable)return <>{separator}<button role="menuitem" aria-disabled="true" aria-labelledby={uid+"-l"} aria-describedby={uid+"-d"} className="menu-unavailable" onClick={event=>event.preventDefault()}>
  <span className="mi-label" id={uid+"-l"}>{item.label}</span><small className="mi-hint" id={uid+"-d"}>{item.unavailable}</small></button></>;
 if(!item.items)return <>{separator}<button role={item.checked===undefined?"menuitem":"menuitemcheckbox"} aria-checked={item.checked} aria-keyshortcuts={aria(item.shortcut)} disabled={item.disabled} title={item.title} onClick={()=>pick(item)}>{content}</button></>;
 const closeSub=()=>{setSub(false);button.current?.focus()};
 const keys=(event:KeyboardEvent<HTMLDivElement>)=>{
  // Everything inside a submenu is handled here so the parent menu's own key handling stays out of it.
  event.stopPropagation();
  const items=ownItems(event.currentTarget),index=items.indexOf(document.activeElement as HTMLButtonElement);
  if(event.key==="Escape"||event.key==="ArrowLeft"){event.preventDefault();closeSub()}
  else if(event.key==="ArrowDown"||event.key==="ArrowUp"){event.preventDefault();items[(index+(event.key==="ArrowDown"?1:-1)+items.length)%items.length]?.focus()}
 };
 return <>{separator}<div ref={wrap} className="menu-sub" onMouseEnter={()=>{if(!item.disabled)setSub(true)}} onMouseLeave={()=>{if(!wrap.current?.contains(document.activeElement))setSub(false)}}>
  <button ref={button} role="menuitem" aria-haspopup="menu" aria-expanded={sub} disabled={item.disabled} title={item.title} onClick={()=>{focusChild.current=true;setSub(true)}}
   onKeyDown={event=>{if(event.key==="ArrowRight"||event.key==="Enter"||event.key===" "){event.preventDefault();event.stopPropagation();focusChild.current=true;setSub(true)}}}>{content}</button>
  {sub&&<div className="app-menu-popover menu-submenu" role="menu" aria-label={item.label} onKeyDown={keys}>{item.items.map(child=><MenuRow key={child.label} item={child} pick={pick}/>)}</div>}
 </div></>;
}

// Application menu: each menu opens on click or ArrowDown, closes on selection, outside click or Escape
// (focus returns to its trigger); arrow keys move between items.
// `leading` is an icon-style menu rendered before the others (the hamburger); its trigger uses `ariaLabel` and shows no caret.
export function MenuBar({menus,leading}:{menus:Menu[];leading?:Menu}){
 const [open,setOpen]=useState<string|null>(null),root=useRef<HTMLElement>(null),triggers=useRef<Record<string,HTMLButtonElement|null>>({});
 const close=(focus=false)=>{const was=open;setOpen(null);if(focus&&was)triggers.current[was]?.focus()};
 useEffect(()=>{if(!open)return;const away=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(null)};
  document.addEventListener("pointerdown",away);return()=>document.removeEventListener("pointerdown",away)},[open]);
 useEffect(()=>{if(open)root.current?.querySelector<HTMLButtonElement>(`[data-menu="${open}"] [role^=menuitem]:not(:disabled)`)?.focus()},[open]);
 const keys=(event:KeyboardEvent<HTMLDivElement>)=>{
  const items=ownItems(event.currentTarget),index=items.indexOf(document.activeElement as HTMLButtonElement);
  if(event.key==="Escape"){event.preventDefault();close(true)}
  else if(event.key==="ArrowDown"||event.key==="ArrowUp"){event.preventDefault();items[(index+(event.key==="ArrowDown"?1:-1)+items.length)%items.length]?.focus()}
 };
 return <nav ref={root} className="app-menu" aria-label="Application menu">
  {[...(leading?[leading]:[]),...menus].map(menu=><div className="app-menu-entry" key={menu.label} data-menu={menu.label}>
   <button ref={node=>{triggers.current[menu.label]=node}} aria-haspopup="menu" aria-expanded={open===menu.label} aria-label={menu.ariaLabel} onClick={()=>setOpen(open===menu.label?null:menu.label)}
    onKeyDown={event=>{if(event.key==="ArrowDown"){event.preventDefault();setOpen(menu.label)}if(event.key==="Escape")close(true)}}>{menu.label}{menu.ariaLabel?null:<span className="caret" aria-hidden="true">⌄</span>}</button>
   {open===menu.label&&<div className="app-menu-popover" role="menu" aria-label={menu.ariaLabel?"Main menu":menu.label} onKeyDown={keys}>
    {menu.items.map(item=><MenuRow key={item.label} item={item} pick={chosen=>{setOpen(null);chosen.onSelect?.();
     // Keep keyboard users in place: if the action moved focus nowhere, return it to this menu's trigger.
     requestAnimationFrame(()=>{if(document.activeElement===document.body)triggers.current[menu.label]?.focus()})}}/>)}
   </div>}
  </div>)}
 </nav>;
}
