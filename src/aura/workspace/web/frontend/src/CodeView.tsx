import {useEffect,useState} from "react";
import {CompileInfo,FirmwareInfo} from "./SimulationPanel";

const compileText=(result:CompileInfo)=>result.status==="passed"?`Compiled for ESP32${result.sizeBytes?` (${result.sizeBytes.toLocaleString()} bytes)`:""}`
 :result.status==="toolchain_missing"?`Toolchain missing: ${result.missing||"unknown"}`
 :`Compile failed: ${result.errors?.[0]?.message||"see compiler output"}${result.errors?.[0]?.line?` (line ${result.errors[0].line})`:""}`;
const PIN_LABEL:Record<string,string>={temperature_data:"DS18B20 data",fan_gate:"MOSFET gate"};

// Mount with key={firmware.revisionId}: a new revision starts from the server's own lastCompileCurrent flag.
type Firmware=FirmwareInfo&{fqbn?:string;libraries?:string[];controlBlock?:string;edit?:{revisionId:string;needsReview:boolean}|null};
export function CodeView({firmware,compile,saveEdit,resetEdit}:{firmware:Firmware;compile:()=>Promise<CompileInfo>;saveEdit?:(block:string)=>Promise<void>;resetEdit?:()=>Promise<void>}){
 const [draft,setDraft]=useState(firmware.controlBlock||""),[editError,setEditError]=useState(""),[saving,setSaving]=useState(false);
 useEffect(()=>setDraft(firmware.controlBlock||""),[firmware.controlBlock]);
 const save=async(action:()=>Promise<void>)=>{setSaving(true);setEditError("");try{await action()}catch(failure){setEditError((failure as Error).message)}finally{setSaving(false)}};
 const [result,setResult]=useState<CompileInfo|null>(firmware.lastCompile??null),[current,setCurrent]=useState(!!firmware.lastCompileCurrent);
 const [compiling,setCompiling]=useState(false),[error,setError]=useState("");
 if(!firmware.supported)return <div className="code-canvas" data-testid="code-view"><section className="code-unsupported"><h2>No firmware for this design</h2><ul>{firmware.reasons.map(reason=><li key={reason}>{reason}</li>)}</ul></section></div>;
 const run=async()=>{setCompiling(true);setError("");try{const next=await compile();setResult(next);setCurrent(next.revisionId===firmware.revisionId)}catch(failure){setError((failure as Error).message)}finally{setCompiling(false)}};
 const status=compiling?"Compiling…":error?`Compile request failed: ${error}`:!result?"Not compiled yet":`${compileText(result)}${current?"":" — compiled for an earlier revision, not the current design revision"}`;
 const lines=(firmware.source||"").split("\n");
 return <div className="code-canvas" data-testid="code-view">
  <section className="code-editor"><header><b>aura_fan.ino</b><span>Generated from revision {firmware.revisionId}</span></header>
   <div className="code-body"><pre className="code-gutter" data-testid="code-gutter" aria-hidden="true">{lines.map((_,index)=>index+1).join("\n")}</pre><pre className="code-source" data-testid="code-source">{firmware.source}</pre></div></section>
  <aside className="code-side">
   {!!firmware.addedWithoutDriver?.length&&<section className="added-without-driver" data-testid="added-without-driver"><h3>Added parts</h3><ul>{firmware.addedWithoutDriver.map(part=><li key={part.semanticId}><b>{part.name}</b> · GPIO{part.gpio} — Pin assigned — no generated driver yet</li>)}</ul></section>}
   {firmware.controlBlock!==undefined&&saveEdit&&<section className="code-edit"><h3>Control rule</h3>
    {firmware.edit&&<p className="edit-badge" data-testid="edit-badge">Edited fanControl</p>}
    {firmware.edit?.needsReview&&<p className="tone-warn" role="status">The design changed since this edit. Review it before compiling.</p>}
    <textarea aria-label="Edit fanControl" spellCheck={false} value={draft} onChange={event=>setDraft(event.target.value)} rows={8}/>
    <small>Only this function is editable. Pins, thresholds and board setup stay generated from the design.</small>
    <div className="code-edit-actions"><button onClick={()=>save(()=>saveEdit(draft))} disabled={saving||draft===firmware.controlBlock}>Save edit</button>
     {firmware.edit&&resetEdit&&<button onClick={()=>save(resetEdit)} disabled={saving}>Reset to generated</button>}</div>
    {editError&&<p className="tone-warn" role="alert">{editError}</p>}</section>}
   <section><h3>Build</h3><button className="primary" onClick={run} disabled={compiling}>COMPILE</button>
    <p data-testid="fw-status" className={result?.status==="passed"&&current?"tone-pass":result?"tone-warn":""}>{status}</p></section>
   <section><h3>Pins</h3><dl>{Object.entries(firmware.pins||{}).flatMap(([name,pin])=>[<dt key={`${name}-t`}>{PIN_LABEL[name]||name}</dt>,<dd key={`${name}-d`}>GPIO{pin}</dd>])}</dl></section>
   <section><h3>Board</h3><p className="mono">{firmware.fqbn||"esp32:esp32:esp32"}</p></section>
   <section><h3>Libraries</h3><ul>{(firmware.libraries||[]).map(library=><li className="mono" key={library}>{library}</li>)}</ul></section>
  </aside>
 </div>;
}
