export const slotBadge=(source:string)=>source==="user"?"You said":source==="default"?"Default":"Assumed";

// Same rule as the backend's ready_to_propose; the backend still decides.
export function canPropose(session:any):boolean{
 const req=session?.requirements;if(!req)return false;
 return req.function?.status==="agreed"&&Boolean(req.power?.value)&&req.power?.status!=="open"&&session.scope?.status==="IN_SCOPE";
}

export function costLine(cost:{totalUsd:number;estimate?:boolean;excluded:string[]}):string{
 const n=cost.excluded.length;
 return `Estimate: $${cost.totalUsd.toFixed(2)}`+(n?` · ${n} ${n===1?"part":"parts"} unpriced`:"");
}

const IO_WORDS:Record<string,string>={temp:"temperature",soil:"soil moisture",light:"light level",motion:"motion",button:"button"};
const ioWord=(id:string)=>{const [slug,n]=[id.replace(/_\d+$/,""),Number(id.match(/_(\d+)$/)?.[1]??1)];return `${IO_WORDS[slug]??slug}${n>1?` ${n}`:""}`};

// Plain-words form of one control rule, as approved on the proposal card.
export function ruleSentence(rule:import("./rules").Rule,ios:{id:string;value:string|null;unit:string}[]):string{
 const input=ios.find(io=>io.id===rule.input),output=ios.find(io=>io.id===rule.output),unit=input?.unit?` ${input.unit}`:"";
 const bool=output?.value==="bool"||typeof rule.onValue==="boolean";
 const action=bool?`turn ${ioWord(rule.output)} ${rule.onValue?"on":"off"}`:`set ${ioWord(rule.output)} to ${rule.onValue}°`;
 const back=bool?`${rule.offValue?"on":"off"} again`:`back to ${rule.offValue}°`;
 const condition=rule.when==="above"||rule.when==="below"?`is ${rule.when} ${rule.threshold}${unit}`:`is ${rule.when}`;
 const release=rule.when==="on"||rule.when==="off"?`${back} when it is ${rule.when==="on"?"off":"on"}`
  :rule.release!==null?`${back} ${rule.when==="above"?"below":"above"} ${rule.release}${unit}`:`${back.replace(/ again$/,"")} otherwise`;
 return `When ${ioWord(rule.input)} ${condition}, ${action} (${release}${rule.minOnSeconds?`, at least ${rule.minOnSeconds} s`:""})`;
}
