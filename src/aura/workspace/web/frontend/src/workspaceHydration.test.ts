import {describe,expect,it} from "vitest";
import {loadWorkspaceData} from "./workspaceHydration";

describe("loadWorkspaceData",()=>{
 it.each(["assembly","verification","narrations"])("keeps required project data when %s is unavailable",async failed=>{
  const load=async(path:string)=>{
   if(path.endsWith(`/${failed}`))throw Error(`${failed} unavailable`);
   if(path.endsWith("/graph"))return {entities:[{id:"component-controller"}]};
   if(path.includes("/api/projects/project-x")&&!path.endsWith("assembly")&&!path.endsWith("verification")&&!path.endsWith("narrations"))return {projectId:"project-x",revision:1};
   if(path.endsWith("/assembly"))return {parts:[{semanticId:"component-controller"}],relationships:[]};
   if(path.endsWith("/verification"))return {findings:[]};
   return [{text:"ready"}];
  };

  const result=await loadWorkspaceData("project-x",load);

  expect(result.project.projectId).toBe("project-x");
  expect(result.graph.entities).toHaveLength(1);
  expect(result.optionalErrors).toEqual([failed]);
 });

 it("still rejects when the required graph is unavailable",async()=>{
  const load=async(path:string)=>{if(path.endsWith("/graph"))throw Error("graph unavailable");return {projectId:"project-x",revision:1}};
  await expect(loadWorkspaceData("project-x",load)).rejects.toThrow("graph unavailable");
 });
});
