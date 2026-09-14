export type JsonLoader=(path:string)=>Promise<any>;

export type WorkspaceHydration={
 project:any;
 graph:any;
 assembly:any;
 verification:any;
 narrations:any[];
 optionalErrors:string[];
};

const emptyAssembly={parts:[],relationships:[],systems:[],primaryMechanismIds:[],unresolvedMechanicalRelations:[],unresolvedPrimaryMechanism:[]};

export async function loadWorkspaceData(id:string,loadJson:JsonLoader):Promise<WorkspaceHydration>{
 const [project,graph]=await Promise.all([
  loadJson(`/api/projects/${id}`),
  loadJson(`/api/projects/${id}/graph`),
 ]);
 const paths=["assembly","verification","narrations"] as const;
 const settled=await Promise.allSettled(paths.map(path=>loadJson(`/api/projects/${id}/${path}`)));
 const errors=paths.filter((_,index)=>settled[index].status==="rejected");
 const value=(index:number,fallback:any)=>settled[index].status==="fulfilled"?(settled[index] as PromiseFulfilledResult<any>).value:fallback;
 return {
  project,
  graph,
  assembly:value(0,emptyAssembly),
  verification:value(1,{findings:[],summary:{}}),
  narrations:value(2,[]),
  optionalErrors:errors,
 };
}
