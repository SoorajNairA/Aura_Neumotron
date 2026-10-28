// Small helpers for the File menu: download naming and server error text.

export function slugify(text:string){return text.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"").slice(0,48)||"project"}

export function dateStamp(date=new Date()){return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`}

// `attachment; filename="aura-<slug>.zip"` -> `aura-<slug>.zip`, or undefined when the header is missing or cross-origin hidden.
export function filenameFromDisposition(header:string|null|undefined){
 const match=/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header||"");
 if(!match)return undefined;
 try{const name=decodeURIComponent(match[1]).replace(/[\\/]/g,"_");return name||undefined}catch{return match[1].replace(/[\\/]/g,"_")}
}

export function exportName(header:string|null|undefined,fallbackTitle:string){return filenameFromDisposition(header)||`aura-${slugify(fallbackTitle)}.zip`}

// `aura-<slug>.zip` -> `aura-<slug>-local-<date>.zip`
export function localCopyName(exportFilename:string,date=new Date()){return exportFilename.replace(/\.zip$/i,"")+`-local-${dateStamp(date)}.zip`}

// Server import errors arrive as `{detail:{code,message}}`; show the server's wording, with a fallback per status.
export function importErrorMessage(body:any,status:number){
 const detail=body?.detail;
 if(detail&&typeof detail==="object"&&typeof detail.message==="string"&&detail.message)return detail.message;
 if(typeof detail==="string"&&detail)return detail;
 return status===413?"That file is too large to import.":"The project could not be imported.";
}

// fetch -> blob -> temporary link. Works in the browser and in sandboxed Electron, which saves it through its download handling.
export function saveBlob(blob:Blob,filename:string){
 const url=URL.createObjectURL(blob),link=document.createElement("a");
 link.href=url;link.download=filename;link.style.display="none";document.body.appendChild(link);link.click();link.remove();
 window.setTimeout(()=>URL.revokeObjectURL(url),10_000);
}
