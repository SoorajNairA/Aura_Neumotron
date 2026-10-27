import {useEffect,useState} from "react";
import {evidenceText,Port,portLabel,Serial,Upload,uploadText} from "./hardware";
import {FirmwareInfo} from "./SimulationPanel";

export function BuildView({api,projectId,firmware,serial}:{api:string;projectId:string;firmware:FirmwareInfo;serial:Serial}){
 const [ports,setPorts]=useState<Port[]>([]),[missing,setMissing]=useState<string|null>(null),[port,setPort]=useState("");
 const [confirming,setConfirming]=useState(false),[uploading,setUploading]=useState(false),[upload,setUpload]=useState<Upload>(),[uploadError,setUploadError]=useState("");
 const refresh=async()=>{const body=await fetch(`${api}/api/hardware/ports`).then(r=>r.json()).catch(()=>({ports:[],toolchainMissing:null}));
  setPorts(body.ports||[]);setMissing(body.toolchainMissing);setPort(current=>current&&body.ports.some((p:Port)=>p.address===current)?current:(body.ports.find((p:Port)=>p.likelyEsp32||p.fake)||body.ports[0])?.address||"")};
 useEffect(()=>{refresh()},[api]);
 const write=async()=>{setConfirming(false);setUploading(true);setUploadError("");setUpload(undefined);
  try{const response=await fetch(`${api}/api/projects/${projectId}/firmware/upload`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({port})});
   const body=await response.json().catch(()=>undefined);
   if(!response.ok)setUploadError(body?.detail?.message||body?.detail?.code||`HTTP ${response.status}`);else setUpload(body)}
  finally{setUploading(false)}};
 const {state}=serial,selected=ports.find(p=>p.address===port),monitoring=state.running&&state.port===port;
 const log=state.lines.slice(-200);
 return <div className="code-canvas build-canvas" data-testid="build-view">
  <section className="build-main">
   <h2>Build on a board</h2>
   <p className="build-evidence" data-testid="hardware-evidence">{evidenceText(state.running&&state.fake?null:state.evidence??firmware.hardwareEvidence,state.running&&state.fake)}</p>
   {state.wrongRevision&&<p className="tone-warn" role="alert" data-testid="wrong-revision">Board runs revision {state.wrongRevision.board}, not the current design ({state.wrongRevision.current}). Upload to update it.</p>}
   <h3>Serial monitor (115200 baud)</h3>
   <ol className="serial-log" data-testid="serial-log">{log.map(line=><li key={line.seq} className={line.telemetry?"telemetry":""}><time>{line.time.slice(11,19)}</time>{line.text}</li>)}</ol>
   {!log.length&&<p className="empty-copy">{state.running?"Waiting for output…":"Start the monitor to see what the board prints."}</p>}
  </section>
  <aside className="code-side">
   <section><h3>USB port</h3>
    {missing&&<p className="tone-warn">arduino-cli not found: ports cannot be listed.</p>}
    <select aria-label="USB port" data-testid="port-select" value={port} onChange={event=>setPort(event.target.value)}>
     {!ports.length&&<option value="">No ports found</option>}{ports.map(p=><option key={p.address} value={p.address}>{portLabel(p)}</option>)}</select>
    <button onClick={refresh}>Refresh ports</button>
    {selected?.fake&&<p className="tone-warn">Fake board (test) — not hardware evidence</p>}</section>
   <section><h3>Upload</h3>
    {!confirming?<button className="primary" disabled={!port||uploading||monitoring} onClick={()=>setConfirming(true)}>{uploading?"Uploading…":"UPLOAD"}</button>
     :<div data-testid="upload-confirm"><p>This writes the firmware to the board on {port}.</p><button className="primary" onClick={write}>Write to board</button><button onClick={()=>setConfirming(false)}>Cancel</button></div>}
    {monitoring&&<small>Stop the monitor to upload on this port.</small>}
    {upload&&<p data-testid="upload-status" className={upload.status==="uploaded"?"tone-pass":"tone-warn"}>{uploadText(upload)}</p>}
    {uploadError&&<p data-testid="upload-status" className="tone-warn" role="alert">{uploadError}</p>}
    <small>Upload needs a passing compile of this revision ({firmware.lastCompileCurrent&&firmware.lastCompile?.status==="passed"?"done":"compile in the Code space"}).</small></section>
   <section><h3>Monitor</h3>
    {state.running?<button onClick={serial.stop}>Stop monitor</button>:<button disabled={!port} onClick={()=>serial.start(port)}>Start monitor</button>}
    {serial.error&&<p className="tone-warn" role="alert">{serial.error}</p>}</section>
  </aside>
 </div>;
}
