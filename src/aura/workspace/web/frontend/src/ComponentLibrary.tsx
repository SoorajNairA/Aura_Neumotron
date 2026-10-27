import {useEffect,useMemo,useRef,useState} from "react";
import {CatalogueItem,factLabel,filterParts,priceLabel} from "./libraryHelpers";

type Props={api:string;onClose:()=>void;onAdd:(ids:string[])=>Promise<string|undefined>};

export function ComponentLibrary({api,onClose,onAdd}:Props){
 const [items,setItems]=useState<CatalogueItem[]>([]),[error,setError]=useState<string>();
 const [query,setQuery]=useState(""),[family,setFamily]=useState<string|null>(null);
 const [picked,setPicked]=useState<string[]>([]),[busy,setBusy]=useState(false);
 const search=useRef<HTMLInputElement>(null);
 useEffect(()=>{
  fetch(`${api}/api/catalogue`).then(r=>r.ok?r.json():Promise.reject(new Error(`HTTP_${r.status}`))).then(setItems).catch(e=>setError(`Catalogue could not load: ${e.message||e}`));
  search.current?.focus();
 },[api]);
 const families=useMemo(()=>[...new Set(items.map(i=>i.family))].sort(),[items]);
 const shown=filterParts(items,query,family);
 return <aside className="component-library" role="dialog" aria-label="Component library" onKeyDown={e=>{if(e.key==="Escape")onClose()}}>
  <header><h2>Component library</h2><button aria-label="Close component library" onClick={onClose}>×</button></header>
  <input ref={search} aria-label="Search parts" placeholder="Search parts" value={query} onChange={e=>setQuery(e.target.value)}/>
  <div className="family-chips" role="group" aria-label="Filter by family">
   <button className={family===null?"active":""} onClick={()=>setFamily(null)}>All</button>
   {families.map(f=><button key={f} className={family===f?"active":""} onClick={()=>setFamily(family===f?null:f)}>{f.replace(/_/g," ")}</button>)}
  </div>
  {error&&<p className="library-error" role="alert" data-testid="library-error">{error}</p>}
  <ul className="library-rows">{shown.map(item=><li key={item.componentDefinitionId} data-testid="library-row">
   <label><input type="checkbox" aria-label={`Select ${item.partNumber}`} checked={picked.includes(item.componentDefinitionId)} onChange={e=>setPicked(p=>e.target.checked?[...p,item.componentDefinitionId]:p.filter(id=>id!==item.componentDefinitionId))}/> <b>{item.partNumber}</b></label><span>{item.manufacturer} · {item.family.replace(/_/g," ")}</span>
   <small>{[factLabel(item.properties.supply_voltage_range),factLabel(item.properties.current),factLabel(item.properties.dimensions)].filter(Boolean).join(" · ")}</small>
   <small className="price">{priceLabel(item)}</small>
  </li>)}</ul>
  {!error&&items.length>0&&shown.length===0&&<p>No parts match.</p>}
  {picked.length>0&&<button className="primary library-add" disabled={busy} onClick={async()=>{setBusy(true);setError(undefined);const problem=await onAdd(picked).finally(()=>setBusy(false));if(problem)setError(problem)}}>Add {picked.length} to design</button>}
 </aside>;
}
