import {useEffect,useMemo,useRef,useState} from "react";
import {CatalogueItem,factLabel,filterParts,priceLabel} from "./libraryHelpers";

type Props={api:string;onClose:()=>void};

export function ComponentLibrary({api,onClose}:Props){
 const [items,setItems]=useState<CatalogueItem[]>([]),[error,setError]=useState<string>();
 const [query,setQuery]=useState(""),[family,setFamily]=useState<string|null>(null);
 const search=useRef<HTMLInputElement>(null);
 useEffect(()=>{
  fetch(`${api}/api/catalogue`).then(r=>r.ok?r.json():Promise.reject(new Error(`HTTP_${r.status}`))).then(setItems).catch(e=>setError(String(e.message||e)));
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
  {error&&<p className="library-error" role="alert">Catalogue could not load: {error}</p>}
  <ul className="library-rows">{shown.map(item=><li key={item.componentDefinitionId} data-testid="library-row">
   <b>{item.partNumber}</b><span>{item.manufacturer} · {item.family.replace(/_/g," ")}</span>
   <small>{[factLabel(item.properties.supply_voltage_range),factLabel(item.properties.current),factLabel(item.properties.dimensions)].filter(Boolean).join(" · ")}</small>
   <small className="price">{priceLabel(item)}</small>
  </li>)}</ul>
  {!error&&items.length>0&&shown.length===0&&<p>No parts match.</p>}
 </aside>;
}
