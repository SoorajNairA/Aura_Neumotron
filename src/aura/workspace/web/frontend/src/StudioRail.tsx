import {useState} from "react";
import {ComponentGroup,GROUP_ORDER,componentGroup,partNumber} from "./studio";

type RailPart={semanticId:string;label:string;family?:string;subsystem:string};
type Props={projectName:string;objective?:string;parts:RailPart[];entities:any[];findings:any[];selected:string|null;
 onSelect:(id:string)=>void;onIsolate:(subsystem:string)=>void;onOpenChecks:()=>void;thumbnails?:Record<string,string>};

// A finding needs attention when it is not passed: failed, or reported at warning level or above.
export const attentionCount=(findings:any[])=>findings.filter(f=>f.status==="failed"||["WARN","ERROR","CRITICAL"].includes(String(f.severity).toUpperCase())).length;

export function StudioRail({projectName,objective,parts,entities,findings,selected,onSelect,onIsolate,onOpenChecks,thumbnails={}}:Props){
 const [query,setQuery]=useState(""),[collapsed,setCollapsed]=useState<Set<ComponentGroup>>(new Set());
 const byId=new Map(entities.map(entity=>[entity.id,entity]));
 const familyOf=(part:RailPart)=>part.family||byId.get(part.semanticId)?.metadata?.family;
 const needle=query.trim().toLowerCase();
 const visible=parts.filter(part=>!needle||[part.label,familyOf(part),partNumber(byId.get(part.semanticId))].some(value=>String(value||"").toLowerCase().includes(needle)));
 const attention=attentionCount(findings);
 return <div className="studio-rail">
  <header className="rail-project"><small>ENGINEERING PROJECT</small><h1>{projectName}</h1>{objective&&<p>{objective}</p>}</header>
  <div className="rail-components-heading"><span>COMPONENTS <b>{parts.length}</b></span>
   <input data-testid="rail-search" type="search" placeholder="Search" aria-label="Search components" value={query} onChange={event=>setQuery(event.target.value)}/></div>
  <div className="semantic-parts">
   {!parts.length&&<p className="rail-empty">No components yet. Planning did not produce a buildable design.</p>}
   {GROUP_ORDER.map(group=>{const members=visible.filter(part=>componentGroup(familyOf(part))===group);if(!members.length)return null;const closed=collapsed.has(group);
    return <section className="rail-group" key={group} data-testid={`rail-group-${group}`}>
     <button className="rail-group-heading" aria-expanded={!closed} onClick={()=>setCollapsed(previous=>{const next=new Set(previous);next.has(group)?next.delete(group):next.add(group);return next})}><span>{closed?"›":"⌄"} {group}</span><b>{members.length}</b></button>
     {!closed&&members.map(part=>{const family=familyOf(part)||"part";const thumb=thumbnails[family];
      return <div className={`rail-part ${selected===part.semanticId?"selected":""}`} key={part.semanticId}>
       <button className="rail-part-main" aria-label={`${part.label} ${part.semanticId}`} onClick={()=>onSelect(part.semanticId)}>
        {thumb?<img src={thumb} alt=""/>:<span className={`rail-icon icon-${componentGroup(family).toLowerCase()}`} aria-hidden="true"/>}
        <span className="rail-part-text"><b>{part.label||part.semanticId}</b><small>{partNumber(byId.get(part.semanticId))||family}</small></span>
       </button>
       <button className="rail-part-more" title="Isolate in 3D" aria-label={`Isolate ${part.label}`} onClick={()=>onIsolate(part.subsystem)}>⋯</button>
      </div>})}
    </section>})}
  </div>
  <button className="rail-add" disabled title="Coming next">＋ Add component</button>
  {attention>0&&<button className="checks-card" data-testid="checks-card" onClick={onOpenChecks}><b>{attention} {attention===1?"check needs":"checks need"} attention</b><span>Open design checks →</span></button>}
 </div>;
}
