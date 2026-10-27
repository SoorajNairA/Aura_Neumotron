import {useCallback,useEffect,useRef,useState} from "react";
import {modelBadge} from "./studio";

const API=(typeof window!=="undefined"?(window as any).auraDesktop?.apiUrl?.replace(/\/$/,""):"")||import.meta.env.VITE_AURA_API_URL||"";

export type ModelKind="nebius"|"openai_compatible"|"ollama_local";
export type ModelProfile={profileId:string;label:string;kind:ModelKind;baseUrl:string;model:string;hasKey:boolean;builtIn?:boolean};
export type ProfilesPayload={active:string|null;activeSource:"profile"|"environment";environmentProvider?:string;profiles:ModelProfile[]};
type TestResult={ok:boolean;code?:string;message?:string;latencyMs?:number};

export const KIND_LABEL:Record<ModelKind,string>={nebius:"Nebius",openai_compatible:"OpenAI-compatible",ollama_local:"Ollama (local)"};
const KIND_HINT:Record<ModelKind,{url:string;model:string}>={nebius:{url:"https://api.tokenfactory.nebius.com/v1/",model:"nvidia/nemotron-3-super-120b-a12b"},openai_compatible:{url:"https://api.openai.com/v1",model:"gpt-4o-mini"},ollama_local:{url:"http://localhost:11434",model:"llama3.1"}};
const TEST_TITLE:Record<string,string>={MODEL_AUTHENTICATION:"Authentication rejected",MODEL_TIMEOUT:"Timed out",MODEL_UNAVAILABLE:"Unreachable or failed",MODEL_RESPONSE_INVALID:"Malformed response",PROFILE_KEY_MISSING:"No API key"};

export const slugify=(label:string,taken:string[])=>{
 const base=label.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"").slice(0,40)||"model";
 let id=base,n=2;while(taken.includes(id))id=`${base}-${n++}`;return id;
};
export const testSummary=(result:TestResult)=>result.ok?`Connected · ${result.latencyMs??0} ms`:`${TEST_TITLE[result.code||""]||"Failed"}: ${result.message||"no details"}`;

async function call(path:string,init?:RequestInit){
 const response=await fetch(`${API}${path}`,init);
 if(response.status===204)return undefined;
 const body=await response.json().catch(()=>undefined);
 if(!response.ok){const detail=body?.detail;const text=detail?.errors?.length?detail.errors.join("; "):detail?.message||`Request failed (${response.status})`;throw new Error(text)}
 return body;
}
const send=(method:string,payload:unknown)=>({method,headers:{"content-type":"application/json"},body:JSON.stringify(payload)});

export function useModelProfiles(reloadKey:unknown=0){
 const [data,setData]=useState<ProfilesPayload>(),[error,setError]=useState("");
 const reload=useCallback(async()=>{try{setData(await call("/api/model-profiles"));setError("")}catch(failure){setError((failure as Error).message)}},[]);
 useEffect(()=>{void reload()},[reload,reloadKey]);
 return {data,error,reload,setData};
}

// Header badge: shows the model that planned the project; opens a menu to pick the active profile or open settings.
export function ModelBadge({project,onOpenSettings,reloadKey}:{project:any;onOpenSettings:()=>void;reloadKey?:unknown}){
 const [open,setOpen]=useState(false),[error,setError]=useState(""),root=useRef<HTMLSpanElement>(null);
 const {data,reload,setData}=useModelProfiles(`${reloadKey}-${open}`);
 const activeLabel=data?.profiles.find(profile=>profile.profileId===data.active)?.label;
 useEffect(()=>{
  if(!open)return;
  const key=(event:KeyboardEvent)=>{if(event.key==="Escape")setOpen(false)};
  const pointer=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false)};
  document.addEventListener("keydown",key);document.addEventListener("pointerdown",pointer);
  return()=>{document.removeEventListener("keydown",key);document.removeEventListener("pointerdown",pointer)};
 },[open]);
 const choose=async(profileId:string)=>{try{setData(await call("/api/model-profiles/active",send("POST",{profileId})));setError("");setOpen(false)}catch(failure){setError((failure as Error).message);void reload()}};
 return <span className="model-menu" ref={root}>
  <button className="model-badge" data-testid="model-badge" aria-haspopup="menu" aria-expanded={open} title="Model that planned this project. Open to choose the model for new requests." onClick={()=>setOpen(!open)}>{modelBadge(project,activeLabel)}</button>
  {open&&<div role="menu" className="menu-popover model-popover" data-testid="model-menu" aria-label="Model profiles">
   <p className="model-menu-note">{data?(data.activeSource==="environment"?`Using environment setting${data.environmentProvider?` (${data.environmentProvider})`:""}`:"Active for new requests"):"Loading profiles…"}</p>
   {data?.profiles.map(profile=><button key={profile.profileId} role="menuitemradio" aria-checked={data.active===profile.profileId} data-testid={`model-option-${profile.profileId}`} onClick={()=>void choose(profile.profileId)}>
    <span>{data.active===profile.profileId?"✓ ":""}{profile.label}</span><small>{profile.model}{profile.hasKey||profile.kind==="ollama_local"?"":" · no key"}</small></button>)}
   {error&&<p className="model-error" role="alert">{error}</p>}
   <button role="menuitem" onClick={()=>{setOpen(false);onOpenSettings()}}>Model settings…</button>
  </div>}
 </span>;
}

const emptyDraft={profileId:"",label:"",kind:"openai_compatible" as ModelKind,baseUrl:"",model:"",key:""};

export function ModelSettings({onClose,onChanged}:{onClose:()=>void;onChanged?:()=>void}){
 const {data,error:loadError,reload}=useModelProfiles();
 const [draft,setDraft]=useState(emptyDraft),[editing,setEditing]=useState<string|null>(null),[formError,setFormError]=useState(""),[busy,setBusy]=useState(false);
 const [tests,setTests]=useState<Record<string,TestResult|"running">>({}),[notice,setNotice]=useState(""),dialog=useRef<HTMLDivElement>(null);
 useEffect(()=>{dialog.current?.focus();const key=(event:KeyboardEvent)=>{if(event.key==="Escape")onClose()};document.addEventListener("keydown",key);return()=>document.removeEventListener("keydown",key)},[onClose]);
 const changed=async()=>{await reload();onChanged?.()};
 const edit=(profile:ModelProfile)=>{setEditing(profile.profileId);setDraft({profileId:profile.profileId,label:profile.label,kind:profile.kind,baseUrl:profile.baseUrl,model:profile.model,key:""});setFormError("");setNotice("")};
 const reset=()=>{setEditing(null);setDraft(emptyDraft);setFormError("")};
 const run=async(action:()=>Promise<void>)=>{setBusy(true);setFormError("");setNotice("");try{await action()}catch(failure){setFormError((failure as Error).message)}finally{setBusy(false)}};
 const save=()=>run(async()=>{
  const id=editing||slugify(draft.label||draft.model,(data?.profiles||[]).map(profile=>profile.profileId));
  await call(`/api/model-profiles/${encodeURIComponent(id)}`,send("PUT",{label:draft.label||id,kind:draft.kind,baseUrl:draft.baseUrl,model:draft.model}));
  if(draft.key.trim())await call(`/api/model-profiles/${encodeURIComponent(id)}/key`,send("PUT",{key:draft.key}));
  setDraft(current=>({...current,key:""}));setEditing(id);setNotice(draft.key.trim()?"Profile and key saved. The key is stored in the system credential store and is never shown again.":"Profile saved.");await changed();
 });
 const activate=(profileId:string)=>run(async()=>{await call("/api/model-profiles/active",send("POST",{profileId}));await changed()});
 const remove=(profile:ModelProfile)=>run(async()=>{await call(`/api/model-profiles/${encodeURIComponent(profile.profileId)}`,{method:"DELETE"});if(editing===profile.profileId)reset();await changed()});
 const test=async(profileId:string)=>{setTests(current=>({...current,[profileId]:"running"}));try{const result=await call(`/api/model-profiles/${encodeURIComponent(profileId)}/test`,{method:"POST"});setTests(current=>({...current,[profileId]:result}))}catch(failure){setTests(current=>({...current,[profileId]:{ok:false,message:(failure as Error).message}}))}};
 const hint=KIND_HINT[draft.kind];
 return <div className="model-settings-backdrop" onMouseDown={event=>{if(event.target===event.currentTarget)onClose()}}>
  <div ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="model-settings-title" className="model-settings" data-testid="model-settings">
   <header><h2 id="model-settings-title">Model settings</h2><button aria-label="Close model settings" onClick={onClose}>×</button></header>
   <p className="model-settings-intro">AURA proposes with the active model; deterministic checks still decide. A failing model is reported, never replaced by another one.</p>
   {data?.activeSource==="environment"&&<p className="model-settings-note" data-testid="model-env-note">No profile is active. New requests use the environment setting{data.environmentProvider?` (${data.environmentProvider})`:""}.</p>}
   {loadError&&<p className="model-error" role="alert">{loadError} <button onClick={()=>void reload()}>Retry</button></p>}
   <ul className="model-profile-list" aria-label="Model profiles">
    {data?.profiles.map(profile=>{const result=tests[profile.profileId];const active=data.active===profile.profileId;return <li key={profile.profileId} data-testid={`profile-${profile.profileId}`} className={active?"active":""}>
     <div><b>{profile.label}</b>{active&&<span className="model-active-tag">Active</span>}<small>{KIND_LABEL[profile.kind]} · {profile.model}</small><small className="mono">{profile.baseUrl}</small>
      <small>{profile.kind==="ollama_local"?(profile.hasKey?"Key saved":"No key needed"):profile.hasKey?"Key saved":"No key saved"}</small></div>
     <div className="model-profile-actions">
      <button onClick={()=>void test(profile.profileId)} disabled={result==="running"}>{result==="running"?"Testing…":"Test"}</button>
      <button onClick={()=>void activate(profile.profileId)} disabled={busy||active}>{active?"In use":"Use"}</button>
      <button onClick={()=>edit(profile)}>Edit</button>
      {!profile.builtIn&&<button onClick={()=>void remove(profile)} disabled={busy}>Delete</button>}
     </div>
     {result&&result!=="running"&&<p role="status" data-testid={`test-result-${profile.profileId}`} className={result.ok?"tone-pass":"tone-warn"}>{testSummary(result)}</p>}
    </li>})}
   </ul>
   <form className="model-form" data-testid="model-form" onSubmit={event=>{event.preventDefault();void save()}} autoComplete="off">
    <h3>{editing?`Edit ${editing}`:"Add a model profile"}</h3>
    <label>Name<input value={draft.label} onChange={event=>setDraft({...draft,label:event.target.value})} placeholder="Work OpenAI"/></label>
    <label>Kind<select value={draft.kind} disabled={!!editing} onChange={event=>setDraft({...draft,kind:event.target.value as ModelKind})}>{(Object.keys(KIND_LABEL) as ModelKind[]).map(kind=><option key={kind} value={kind}>{KIND_LABEL[kind]}</option>)}</select></label>
    <label>Base URL<input value={draft.baseUrl} onChange={event=>setDraft({...draft,baseUrl:event.target.value})} placeholder={hint.url} inputMode="url"/></label>
    <label>Model<input value={draft.model} onChange={event=>setDraft({...draft,model:event.target.value})} placeholder={hint.model}/></label>
    <label>API key{draft.kind==="ollama_local"?" (optional)":""}<input type="password" value={draft.key} autoComplete="new-password" onChange={event=>setDraft({...draft,key:event.target.value})} placeholder={editing?"Leave blank to keep the saved key":"Stored in the system credential store"}/></label>
    <p className="model-settings-note">https is required except for localhost. The key is write-only: it is never shown again.</p>
    {formError&&<p className="model-error" role="alert" data-testid="model-form-error">{formError}</p>}
    {notice&&<p role="status" className="tone-pass" data-testid="model-form-notice">{notice}</p>}
    <div className="model-form-actions"><button type="submit" className="primary" disabled={busy}>{editing?"Save changes":"Save profile"}</button>{editing&&<button type="button" onClick={reset}>New profile</button>}</div>
   </form>
  </div>
 </div>;
}
