import {useCallback,useEffect,useRef,useState} from "react";

export type Port={address:string;label:string;likelyEsp32:boolean;fake:boolean;vid?:string|null;pid?:string|null};
export type Evidence={port:string;revisionId:string;lines:number;firstSeen:string;agreement:string};
export type Upload={status:"uploaded"|"failed"|"toolchain_missing";port:string;revisionId:string;uploadedAt:string;errors:string[];fake:boolean;hint:string|null};
export type SerialLine={seq:number;time:string;text:string;telemetry:Record<string,any>|null};
export type SerialState={running:boolean;port:string|null;fake:boolean;lines:SerialLine[];wrongRevision:{board:string;current:string}|null;evidence:Evidence|null};

const utc=(iso:string)=>`${iso.slice(0,16).replace("T"," ")} UTC`;
// Evidence counts only for the revision the board should be running now; older evidence is history, not a claim.
export const evidenceText=(evidence:Evidence|null|undefined,fake=false,expected?:string|null)=>fake?"Fake board (test) — not hardware evidence"
 :evidence&&expected&&evidence.revisionId!==expected?`Not tried on hardware (last observed: revision ${evidence.revisionId})`
 :evidence?`Observed on hardware: ${evidence.port}, revision ${evidence.revisionId}, ${evidence.lines} lines, ${utc(evidence.firstSeen)}`:"Not tried on hardware";
export const portLabel=(port:Port)=>port.fake?port.label:port.likelyEsp32?`${port.label} — likely ESP32 (unverified)`:port.label;
export const uploadText=(upload:Upload)=>upload.status==="uploaded"
 ?`Uploaded revision ${upload.revisionId} to ${upload.port} at ${utc(upload.uploadedAt)} — not yet observed running${upload.fake?" (fake board, test)":""}`
 :upload.status==="toolchain_missing"?"Upload needs arduino-cli; see the README firmware toolchain section."
 :`Upload failed: ${upload.errors[0]||"see output"}.${upload.hint?` ${upload.hint}`:""}`;

// A poll answer for a project the user already left is dropped, so logs and state never mix across projects.
export function applyPoll(state:SerialState,body:SerialState,requested:string,active:string|undefined):SerialState{
 return requested!==active?state:{...body,lines:[...state.lines,...body.lines].slice(-500)};
}

const IDLE:SerialState={running:false,port:null,fake:false,lines:[],wrongRevision:null,evidence:null};
const detail=async(response:Response)=>{const body=await response.json().catch(()=>undefined);return body?.detail?.message||body?.detail?.code||`HTTP ${response.status}`};

// One serial session per project, shared by the Build and Simulation spaces; polls once a second while running.
export function useSerial(api:string,projectId:string|undefined){
 const [state,setState]=useState<SerialState>(IDLE),[error,setError]=useState<string>(),[pending,setPending]=useState(false);
 const after=useRef(0),active=useRef(projectId);active.current=projectId;
 const poll=useCallback(async()=>{
  if(!projectId)return;
  const response=await fetch(`${api}/api/projects/${projectId}/serial?after=${after.current}`).catch(()=>undefined);
  if(!response?.ok||active.current!==projectId)return;
  const body:SerialState=await response.json();const fresh=body.lines||[];
  if(active.current!==projectId)return;
  if(fresh.length)after.current=fresh[fresh.length-1].seq;
  setState(current=>applyPoll(current,{...body,lines:fresh},projectId,active.current));
 },[api,projectId]);
 useEffect(()=>{after.current=0;setState(IDLE);setError(undefined);poll()},[projectId,poll]);
 useEffect(()=>{if(!state.running)return;const timer=setInterval(poll,1000);return()=>clearInterval(timer)},[state.running,poll]);
 // Leaving the project stops its monitor so no serial process is left behind.
 useEffect(()=>()=>{if(projectId)fetch(`${api}/api/projects/${projectId}/serial/stop`,{method:"POST"}).catch(()=>undefined)},[api,projectId]);
 const start=async(port:string)=>{if(pending)return;setPending(true);setError(undefined);after.current=0;setState({...IDLE});
  try{const response=await fetch(`${api}/api/projects/${projectId}/serial/start`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({port})});
   if(!response.ok){setError(await detail(response));return}await poll()}finally{setPending(false)}};
 const stop=async()=>{await fetch(`${api}/api/projects/${projectId}/serial/stop`,{method:"POST"}).catch(()=>undefined);await poll()};
 return {state,error,start,stop,pending};
}
export type Serial=ReturnType<typeof useSerial>;
