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
