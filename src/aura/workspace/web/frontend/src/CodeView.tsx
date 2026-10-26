import {useState} from "react";
import {CompileInfo,FirmwareInfo} from "./SimulationPanel";

const compileText=(result:CompileInfo)=>result.status==="passed"?`Compiled for ESP32${result.sizeBytes?` (${result.sizeBytes.toLocaleString()} bytes)`:""}`
 :result.status==="toolchain_missing"?`Toolchain missing: ${result.missing||"unknown"}`
 :`Compile failed: ${result.errors?.[0]?.message||"see compiler output"}${result.errors?.[0]?.line?` (line ${result.errors[0].line})`:""}`;
const PIN_LABEL:Record<string,string>={temperature_data:"DS18B20 data",fan_gate:"MOSFET gate"};

// Mount with key={firmware.revisionId}: a new revision starts from the server's own lastCompileCurrent flag.
export function CodeView({firmware,compile}:{firmware:FirmwareInfo&{fqbn?:string;libraries?:string[]};compile:()=>Promise<CompileInfo>}){
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
   <section><h3>Build</h3><button className="primary" onClick={run} disabled={compiling}>COMPILE</button>
    <p data-testid="fw-status" className={result?.status==="passed"&&current?"tone-pass":result?"tone-warn":""}>{status}</p></section>
   <section><h3>Pins</h3><dl>{Object.entries(firmware.pins||{}).flatMap(([name,pin])=>[<dt key={`${name}-t`}>{PIN_LABEL[name]||name}</dt>,<dd key={`${name}-d`}>GPIO{pin}</dd>])}</dl></section>
   <section><h3>Board</h3><p className="mono">{firmware.fqbn||"esp32:esp32:esp32"}</p></section>
   <section><h3>Libraries</h3><ul>{(firmware.libraries||[]).map(library=><li className="mono" key={library}>{library}</li>)}</ul></section>
  </aside>
 </div>;
}
