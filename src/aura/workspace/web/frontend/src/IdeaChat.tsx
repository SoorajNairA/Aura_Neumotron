import {useEffect,useRef,useState} from "react";
import {providerErrorPresentation} from "./presentation";
import {canPropose,costLine,slotBadge} from "./ideaHelpers";

type Props={apiBase:string;idea:string;onApproved:(projectId:string)=>void;onClose:()=>void};
type Failure={code:string;title:string;message:string;details?:string};
const SLOT_LABELS:Record<string,string>={function:"Function",budget:"Budget",power:"Power",connectivity:"Connectivity",dimensions:"Size",environment:"Environment",experience:"Experience"};

// The conversation that turns an idea into agreed requirements and an approved proposal.
export function IdeaChat({apiBase,idea,onApproved,onClose}:Props){
 const [session,setSession]=useState<any>(),[proposal,setProposal]=useState<any>(),[draft,setDraft]=useState("");
 const [busy,setBusy]=useState<string|null>(null),[error,setError]=useState<Failure>(),[retry,setRetry]=useState<(()=>void)|null>(null);
 const started=useRef(false);
 const call=async(path:string,body?:any,label="Thinking…",again?:()=>void)=>{
  setBusy(label);setError(undefined);setRetry(null);
  try{const response=await fetch(`${apiBase}${path}`,{method:"POST",headers:{"content-type":"application/json"},body:body===undefined?undefined:JSON.stringify(body)});
   const payload=await response.json().catch(()=>({}));
   if(!response.ok){setError(providerErrorPresentation(payload,response.status));setRetry(()=>again||null);return undefined}
   return payload}
  catch(failure){setError(providerErrorPresentation({detail:{message:failure instanceof Error?failure.message:""}},0));setRetry(()=>again||null);return undefined}
  finally{setBusy(null)}};
 const start=async()=>{const next=await call("/api/ideas",{idea},"Reading your idea…",start);if(next)setSession(next)};
 useEffect(()=>{if(!started.current){started.current=true;start()}},[]);
 const send=async(text:string)=>{if(!session||!text.trim())return;const next=await call(`/api/ideas/${session.sessionId}/messages`,{text},"Thinking…",()=>send(text));if(next){setSession(next);setDraft("");setProposal(undefined)}};
 const propose=async()=>{const card=await call(`/api/ideas/${session.sessionId}/proposal`,undefined,"Planning the design…",propose);if(card)setProposal(card)};
 const approve=async()=>{const project=await call(`/api/ideas/${session.sessionId}/approve`,{proposalId:proposal.proposalId},"Building the approved design…",approve);if(project?.projectId)onApproved(project.projectId)};
 const scope=session?.scope;
 return <section className="idea-chat" data-testid="idea-chat" aria-label="Design conversation">
  <header className="idea-head"><div><small>DESIGN CONVERSATION</small><h2>{idea}</h2></div><button onClick={onClose}>Back</button></header>
  <div className="idea-body">
   <div className="idea-thread">
    {(session?.messages||[]).map((message:any,index:number)=><p key={index} className={`idea-msg ${message.role}`} data-testid="idea-message">{message.text}</p>)}
    {busy&&<p className="idea-msg pending" role="status">{busy}</p>}
    {error&&<div className="provider-error" role="alert" data-testid="idea-error"><b>{error.title}</b><code>{error.code}</code><p>{error.message}</p>{error.details&&<p>{error.details}</p>}{retry&&<button onClick={retry}>Retry</button>}</div>}
    {scope?.status==="OUT_OF_SCOPE"&&<div className="idea-scope" data-testid="idea-scope"><b>Outside what AURA can design</b>{scope.reasons.map((reason:string)=><p key={reason}>{reason}</p>)}
     {scope.alternative&&<><p>Achievable instead: {scope.alternative}</p><button onClick={()=>send(`Let's do the alternative: ${scope.alternative}`)}>Use this alternative</button></>}</div>}
    {(session?.openQuestions||[]).map((question:any)=><div className="idea-question" key={question.slot+question.question}><p>{question.question}</p>
     {question.suggestedDefault&&<button className="default-chip" data-testid="default-chip" onClick={()=>send(`Use the default for ${question.slot}: ${question.suggestedDefault}`)}>Use {question.suggestedDefault}</button>}
     {question.tradeoff&&<small>Tradeoff: {question.tradeoff}</small>}</div>)}
    <form className="idea-input" onSubmit={event=>{event.preventDefault();send(draft)}}><input aria-label="Reply to AURA" value={draft} onChange={event=>setDraft(event.target.value)} placeholder="Answer or add detail…" disabled={!session||Boolean(busy)}/><button type="submit" disabled={!session||!draft.trim()||Boolean(busy)}>Send</button></form>
   </div>
   <aside className="idea-side">
    <section className="requirements-card" data-testid="requirements-card"><h3>Requirements</h3>
     {Object.entries(SLOT_LABELS).map(([slot,label])=>{const item=session?.requirements?.[slot];return <div className={`req-row ${item?.status||"open"}`} key={slot} data-testid={`slot-${slot}`}><span>{label}</span><b>{item?.value||"—"}</b>{item?.value&&<em>{slotBadge(item.source)}</em>}</div>})}
     {session?.unsupportedNeeds?.length>0&&<p className="req-note">Not supported: {session.unsupportedNeeds.join(", ")}</p>}
     <button className="propose" data-testid="propose-design" disabled={!canPropose(session)||Boolean(busy)} onClick={propose}>Propose design</button>
    </section>
    {proposal&&<section className="proposal-card" data-testid="proposal-card"><h3>Proposed design</h3>
     <ul>{proposal.components.map((part:any)=><li key={part.semanticId}><b>{part.name}</b><span>{part.partNumber||"Generic proxy"}</span>
      <span>{part.price?`$${part.price.usd.toFixed(2)} (${part.price.retrieved})`:"price unavailable"}</span>
      {part.alternatives.length>1&&<details><summary>{part.alternatives.length-1} compatible alternatives (ranked by {proposal.rankedBy})</summary>
       <ul>{part.alternatives.filter((alt:any)=>!alt.selected).map((alt:any)=><li key={alt.componentDefinitionId}>{alt.partNumber} · {alt.priceUsd!=null?`$${alt.priceUsd.toFixed(2)}`:"price unavailable"}</li>)}</ul></details>}</li>)}</ul>
     <p className="cost-total" data-testid="cost-total">{costLine(proposal.cost)}</p>
     {proposal.limitations.length>0&&<details open><summary>Limitations</summary><ul>{proposal.limitations.map((item:string)=><li key={item}>{item}</li>)}</ul></details>}
     {proposal.assumptions.length>0&&<details><summary>Assumptions</summary><ul>{proposal.assumptions.map((item:string)=><li key={item}>{item}</li>)}</ul></details>}
     <div className="proposal-actions"><button data-testid="approve-design" onClick={approve} disabled={Boolean(busy)}>Approve</button><button data-testid="change-design" onClick={()=>setProposal(undefined)} disabled={Boolean(busy)}>Change</button></div>
    </section>}
   </aside>
  </div>
 </section>;
}
