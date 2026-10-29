import {expect,Page,test} from "@playwright/test";
import {mock,project} from "./fanFixture";

// All endpoints are mocked; AURA_E2E_MOCK_ONLY=1 needs no backend.
const MESSAGE="AURA couldn't resolve this engineering architecture reliably.";
const ISSUE="Drive motor is not connected to the wheel or mechanism.";
const failed={...project,projectId:"project-failed",status:"build_incomplete",planningMode:"live_model",generationMessage:MESSAGE,userIssues:[ISSUE],representations:[]};
const retried={...project,projectId:"project-retried",status:"ready"};

function fixtures(id:string,proj:any,parts:any[]){
 return async(page:Page)=>{
  await page.route(`**/api/projects/${id}`,r=>r.fulfill({json:proj}));
  await page.route(`**/api/projects/${id}/revisions`,r=>r.fulfill({json:[{revision:1,summary:"Project created"}]}));
  await page.route(`**/api/projects/${id}/assembly`,r=>r.fulfill({json:{parts,connectors:[],relationships:[]}}));
  await page.route(`**/api/projects/${id}/graph`,r=>r.fulfill({json:{project_id:id,entities:[{id,kind:"project",name:proj.objective}],relationships:[]}}));
  await page.route(`**/api/projects/${id}/verification`,r=>r.fulfill({json:{state:"pass",summary:{},findings:[]}}));
  await page.route(`**/api/projects/${id}/work`,r=>r.fulfill({json:{items:[]}}));
  await page.route(`**/api/projects/${id}/narrations`,r=>r.fulfill({json:[]}));
  await page.route(`**/api/projects/${id}/firmware`,r=>r.fulfill({status:404,json:{detail:"none"}}));
  await page.route(`**/api/projects/${id}/layout`,r=>r.fulfill({json:{layout:{parts:{},wires:{},labels:{}},updatedAt:null}}));
 };
}

async function setup(page:Page){
 await mock(page);
 await page.route("**/api/hardware/ports",r=>r.fulfill({json:{ports:[],toolchainMissing:null}}));
 await page.route("**/api/catalogue",r=>r.fulfill({json:[]}));
 await fixtures("project-failed",failed,[])(page);
 await fixtures("project-retried",retried,[])(page);
 const posts:any[]=[];
 let release:()=>void=()=>{};
 const gate=new Promise<void>(resolve=>{release=resolve});
 await page.route("**/api/projects",async route=>{
  if(route.request().method()==="POST"){posts.push(route.request().postDataJSON());await gate;return route.fulfill({status:201,json:retried})}
  return route.fulfill({json:[failed,project]});
 });
 return {posts,release};
}

test("a build_incomplete project with no parts explains itself and can be retried",async({page})=>{
 const {posts,release}=await setup(page);
 await page.goto("/?projectId=project-failed");
 const card=page.getByRole("alert").filter({hasText:"AURA couldn't build this design"});
 await expect(card).toBeVisible();
 await expect(card).toContainText(MESSAGE);
 await expect(card).toContainText(ISSUE);
 await expect(page.getByText("Your concept is ready")).toHaveCount(0);
 await expect(page.getByText("Planning didn't produce a design")).toBeVisible();
 const retry=card.getByRole("button",{name:"Try again"});
 await retry.click();
 await expect(card.getByText("Planning...")).toBeVisible();
 await expect(card.getByRole("button")).toBeDisabled();
 expect(posts).toHaveLength(1);
 expect(posts[0].objective).toBe(failed.objective);
 expect(typeof posts[0].operationId).toBe("string");
 release();
 await expect(page).toHaveURL(/projectId=project-retried/);
 await expect(page.getByRole("alert").filter({hasText:"AURA couldn't build this design"})).toHaveCount(0);
 await expect(page.getByText("Your concept is ready")).toBeVisible();
});

test("a ready project with parts shows no failure card",async({page})=>{
 await setup(page);
 await page.goto("/?projectId=project-fan");
 await expect(page.getByTestId("three-host")).toBeVisible();
 await expect(page.getByText("AURA couldn't build this design")).toHaveCount(0);
 await expect(page.getByText("Your concept is ready")).toBeVisible();
});
