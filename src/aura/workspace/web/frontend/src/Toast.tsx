import {useEffect} from "react";

export const TOAST_MS=6000;

// Transient bottom-left notice for narration and status changes. Dismissed by its button or after six seconds;
// a new message restarts the timer.
export function Toast({message,onDismiss}:{message:string|undefined;onDismiss:()=>void}){
 useEffect(()=>{if(!message)return;const timer=window.setTimeout(onDismiss,TOAST_MS);return()=>window.clearTimeout(timer)},[message]);
 if(!message)return null;
 return <div className="toast" role="status" data-testid="toast"><b>AURA</b><span>{message}</span><button aria-label="Dismiss" onClick={onDismiss}>×</button></div>;
}
