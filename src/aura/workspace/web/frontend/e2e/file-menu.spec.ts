import {expect,Page,test} from "@playwright/test";
import {mock,project} from "./fanFixture";

// All endpoints are mocked; AURA_E2E_MOCK_ONLY=1 needs no backend.
const other={...project,projectId:"project-b",objective:"Build a weather station",revision:3,updatedAt:"2026-10-28T10:00:00Z"};
const fan={...project,updatedAt:"2026-10-29T09:00:00Z"};
const REASON="Sharing needs a hosted server with access control; not available in this build";
const emptyLayout={parts:{},wires:{},labels:{}};

async function setup(page:Page){
 await mock(page);
 await page.route("**/api/hardware/ports",r=>r.fulfill({json:{ports:[],toolchainMissing:null}}));
 await page.route("**/api/catalogue",r=>r.fulfill({json:[]}));
 // Other project ids need their own fixtures so opening them loads cleanly.
 for(const id of ["project-b","project-copy","project-imported"]){
  const text=id==="project-b"?other.objective:"Design a temperature-controlled desk fan";
  const proj={...project,projectId:id,objective:text};
  await page.route(`**/api/projects/${id}`,r=>r.fulfill({json:proj}));
  await page.route(`**/api/projects/${id}/revisions`,r=>r.fulfill({json:[{revision:1,summary:"Project created"}]}));
  await page.route(`**/api/projects/${id}/assembly`,r=>r.fulfill({json:{parts:[],connectors:[],relationships:[]}}));
  await page.route(`**/api/projects/${id}/graph`,r=>r.fulfill({json:{project_id:id,entities:[{id,kind:"project",name:text}],relationships:[]}}));
  await page.route(`**/api/projects/${id}/verification`,r=>r.fulfill({json:{state:"pass",summary:{},findings:[]}}));
  await page.route(`**/api/projects/${id}/work`,r=>r.fulfill({json:{items:[]}}));
  await page.route(`**/api/projects/${id}/narrations`,r=>r.fulfill({json:[]}));
  await page.route(`**/api/projects/${id}/firmware`,r=>r.fulfill({status:404,json:{detail:"none"}}));
  await page.route(`**/api/projects/${id}/layout`,r=>r.fulfill({json:{layout:emptyLayout,updatedAt:null}}));
 }
 await page.route("**/api/projects",r=>r.fulfill({json:[fan,other]}));
 const puts:any[]=[];
 await page.route("**/api/projects/project-fan/layout",async route=>{
  if(route.request().method()==="PUT"){puts.push(route.request().postDataJSON());return route.fulfill({json:{updatedAt:"2026-10-29T10:00:00Z"}})}
  return route.fulfill({json:{layout:emptyLayout,updatedAt:null}});
 });
 return {puts};
}

const fileMenu=(page:Page)=>page.getByRole("navigation",{name:"Application menu"}).getByRole("button",{name:"File",exact:true});
const dirty=(page:Page)=>page.evaluate(()=>(window as any).__auraSetLayout({parts:{"component-fan":{x:12,y:6}},wires:{},labels:{}}));
async function ready(page:Page,query=""){
 await page.goto(`/?projectId=project-fan${query}`);
 await expect(page.getByTestId("three-host")).toBeVisible();
}

test("File menu lists the real actions with shortcuts, separators and submenus",async({page})=>{
 await setup(page);await ready(page);
 await fileMenu(page).click();
 const menu=page.getByRole("menu",{name:"File"});
 const names=await menu.getByRole("menuitem").evaluateAll(nodes=>nodes.map(n=>n.querySelector(".mi-label")?.textContent||""));
 expect(names).toEqual(["New","Open","Save","Make a copy","Export","Import","Save local copy"]);
 await expect(page.getByRole("menuitem",{name:"Open",exact:true})).toContainText("Ctrl+O");
 await expect(page.getByRole("menuitem",{name:"Save",exact:true})).toContainText("Ctrl+S");
 await expect(menu.getByRole("separator")).toHaveCount(2);
 const exportItem=page.getByRole("menuitem",{name:"Export",exact:true});
 await expect(exportItem).toHaveAttribute("aria-haspopup","menu");
 await exportItem.hover();
 const sub=page.getByRole("menu",{name:"Export"});
 await expect(sub.getByRole("menuitem",{name:"Project ZIP",exact:true})).toBeEnabled();
 const share=sub.getByRole("menuitem",{name:"Shareable link"});
 // Unavailable but reachable: focusable (not natively disabled), aria-disabled, reason visible and described.
 await expect(share).toHaveAttribute("aria-disabled","true");
 await expect(share).not.toHaveAttribute("disabled","");
 await expect(share).toHaveAccessibleDescription(REASON);
 await expect(sub.getByText(REASON)).toBeVisible();
 await page.getByRole("menuitem",{name:"Import",exact:true}).hover();
 await expect(page.getByRole("menu",{name:"Import"}).getByRole("menuitem",{name:"Project ZIP…"})).toBeVisible();
});

test("submenus open with ArrowRight and close with ArrowLeft or Escape without leaving the menu",async({page})=>{
 await setup(page);await ready(page);
 await fileMenu(page).click();
 await page.getByRole("menuitem",{name:"Export",exact:true}).focus();
 await page.keyboard.press("ArrowRight");
 await expect(page.getByRole("menuitem",{name:"Project ZIP",exact:true})).toBeFocused();
 await page.keyboard.press("ArrowLeft");
 await expect(page.getByRole("menuitem",{name:"Export",exact:true})).toBeFocused();
 await expect(page.getByRole("menu",{name:"Export"})).toHaveCount(0);
 await page.keyboard.press("ArrowRight");await page.keyboard.press("Escape");
 await expect(page.getByRole("menuitem",{name:"Export",exact:true})).toBeFocused();
 await expect(page.getByRole("menu",{name:"File"})).toBeVisible();
 await page.keyboard.press("Escape");
 await expect(fileMenu(page)).toBeFocused();
});

test("Ctrl+O opens the Open project dialog; search filters and Create new project starts a design",async({page})=>{
 await setup(page);await ready(page);
 await page.keyboard.press("Control+o");
 const dialog=page.getByRole("dialog",{name:"Open project"});
 await expect(dialog).toBeVisible();
 await expect(dialog).toHaveAttribute("aria-modal","true");
 const search=dialog.getByRole("searchbox");
 await expect(search).toBeFocused();
 await expect(dialog.getByRole("button",{name:/desk fan/i})).toBeVisible();
 await expect(dialog.getByRole("button",{name:/weather station/i})).toBeVisible();
 await search.fill("weather");
 await expect(dialog.getByRole("button",{name:/desk fan/i})).toHaveCount(0);
 await expect(dialog.getByRole("button",{name:/weather station/i})).toBeVisible();
 await expect(dialog.getByRole("button",{name:"Create new project"})).toBeVisible();
 await page.keyboard.press("Escape");
 await expect(dialog).toHaveCount(0);
 await page.keyboard.press("Control+o");
 await page.getByRole("dialog",{name:"Open project"}).getByRole("button",{name:"Create new project"}).click();
 await expect(page.getByRole("heading",{name:"What do you want to build?"})).toBeVisible();
});

test("Open dialog is keyboard navigable and opens the chosen project",async({page})=>{
 await setup(page);await ready(page);
 await fileMenu(page).click();await page.getByRole("menuitem",{name:"Open",exact:true}).click();
 const dialog=page.getByRole("dialog",{name:"Open project"});
 await expect(dialog.getByRole("searchbox")).toBeFocused();
 await page.keyboard.press("ArrowDown");
 await expect(dialog.getByRole("button",{name:/desk fan/i})).toBeFocused();
 await page.keyboard.press("ArrowDown");
 await expect(dialog.getByRole("button",{name:/weather station/i})).toBeFocused();
 await page.keyboard.press("Enter");
 await expect(dialog).toHaveCount(0);
 await expect(page).toHaveURL(/projectId=project-b/);
});

test("Save (menu and Ctrl+S) PUTs the layout and confirms with a Saved toast",async({page})=>{
 const {puts}=await setup(page);await ready(page,"&e2e=1");
 await page.waitForFunction(()=>typeof (window as any).__auraSetLayout==="function");
 await dirty(page);
 await fileMenu(page).click();await page.getByRole("menuitem",{name:"Save",exact:true}).click();
 await expect(page.getByTestId("toast")).toContainText("Saved");
 expect(puts).toHaveLength(1);
 expect(puts[0].layout.parts["component-fan"]).toEqual({x:12,y:6});
 await page.keyboard.press("Control+s");
 await expect.poll(()=>puts.length).toBe(2);
});

test("Make a copy POSTs the copy endpoint and opens the new project",async({page})=>{
 await setup(page);
 let copied=0;
 await page.route("**/api/projects/project-fan/copy",r=>{copied++;return r.fulfill({status:201,json:{...project,projectId:"project-copy",objective:"Design a temperature-controlled desk fan (copy)"}})});
 await ready(page);
 await fileMenu(page).click();await page.getByRole("menuitem",{name:"Make a copy",exact:true}).click();
 await expect(page).toHaveURL(/projectId=project-copy/);
 expect(copied).toBe(1);
});

test("Export and Save local copy download restorable ZIPs",async({page})=>{
 await setup(page);
 await page.route("**/api/projects/project-fan/export",r=>r.fulfill({status:200,body:Buffer.from("PK\u0003\u0004"),headers:{"content-type":"application/zip","content-disposition":'attachment; filename="aura-temperature-controlled-desk-fan.zip"'}}));
 await ready(page);
 await fileMenu(page).click();await page.getByRole("menuitem",{name:"Export",exact:true}).hover();
 const [exported]=await Promise.all([page.waitForEvent("download"),page.getByRole("menuitem",{name:"Project ZIP",exact:true}).click()]);
 expect(exported.suggestedFilename()).toBe("aura-temperature-controlled-desk-fan.zip");
 await fileMenu(page).click();
 const [local]=await Promise.all([page.waitForEvent("download"),page.getByRole("menuitem",{name:"Save local copy",exact:true}).click()]);
 expect(local.suggestedFilename()).toMatch(/^aura-temperature-controlled-desk-fan-local-\d{4}-\d{2}-\d{2}\.zip$/);
});

test("Import posts the ZIP and opens the new project; a rejected file shows the server message",async({page})=>{
 await setup(page);
 let body:Buffer|null=null,type="";
 await page.route("**/api/projects/import",r=>{
  const req=r.request();body=req.postDataBuffer();type=req.headers()["content-type"]||"";
  if(body?.toString()==="bad")return r.fulfill({status:400,json:{detail:{code:"UNSUPPORTED_VERSION",message:"This project file was made by a newer version of AURA."}}});
  return r.fulfill({status:201,json:{...project,projectId:"project-imported",objective:"Imported fan"}});
 });
 await ready(page);
 await fileMenu(page).click();await page.getByRole("menuitem",{name:"Import",exact:true}).hover();
 let [chooser]=await Promise.all([page.waitForEvent("filechooser"),page.getByRole("menuitem",{name:"Project ZIP…"}).click()]);
 await chooser.setFiles({name:"bad.zip",mimeType:"application/zip",buffer:Buffer.from("bad")});
 await expect(page.getByTestId("toast")).toContainText("This project file was made by a newer version of AURA.");
 expect(type).toBe("application/zip");
 await expect(page).toHaveURL(/projectId=project-fan/);
 await fileMenu(page).click();await page.getByRole("menuitem",{name:"Import",exact:true}).hover();
 [chooser]=await Promise.all([page.waitForEvent("filechooser"),page.getByRole("menuitem",{name:"Project ZIP…"}).click()]);
 await chooser.setFiles({name:"good.zip",mimeType:"application/zip",buffer:Buffer.from("PK-good")});
 await expect(page).toHaveURL(/projectId=project-imported/);
});

test("unsaved layout edits ask Save, Discard or Cancel before switching project",async({page})=>{
 const {puts}=await setup(page);await ready(page,"&e2e=1");
 await page.waitForFunction(()=>typeof (window as any).__auraSetLayout==="function");
 await dirty(page);
 const chooseOther=async()=>{
  await page.keyboard.press("Control+o");
  await page.getByRole("dialog",{name:"Open project"}).getByRole("button",{name:/weather station/i}).click();
 };
 await chooseOther();
 const guard=page.getByRole("dialog",{name:"Unsaved changes"});
 await expect(guard).toBeVisible();
 await expect(guard.getByRole("button",{name:"Save",exact:true})).toBeFocused();
 await guard.getByRole("button",{name:"Cancel",exact:true}).click();
 await expect(guard).toHaveCount(0);
 await expect(page).toHaveURL(/projectId=project-fan/);
 expect(puts).toHaveLength(0);
 // Escape also cancels; Save writes the layout, then switches.
 await chooseOther();await page.keyboard.press("Escape");
 await expect(guard).toHaveCount(0);await expect(page).toHaveURL(/projectId=project-fan/);
 await chooseOther();
 await guard.getByRole("button",{name:"Save",exact:true}).click();
 await expect(page).toHaveURL(/projectId=project-b/);
 expect(puts).toHaveLength(1);
});

test("Discard drops the edits and switches; New and Make a copy are guarded too",async({page})=>{
 const {puts}=await setup(page);
 await page.route("**/api/projects/project-fan/copy",r=>r.fulfill({status:201,json:{...project,projectId:"project-copy"}}));
 await ready(page,"&e2e=1");
 await page.waitForFunction(()=>typeof (window as any).__auraSetLayout==="function");
 await dirty(page);
 await fileMenu(page).click();await page.getByRole("menuitem",{name:"New",exact:true}).click();
 const guard=page.getByRole("dialog",{name:"Unsaved changes"});
 await expect(guard).toBeVisible();
 await guard.getByRole("button",{name:"Cancel",exact:true}).click();
 await fileMenu(page).click();await page.getByRole("menuitem",{name:"Make a copy",exact:true}).click();
 await expect(guard).toBeVisible();
 await guard.getByRole("button",{name:"Discard",exact:true}).click();
 await expect(page).toHaveURL(/projectId=project-copy/);
 expect(puts).toHaveLength(0);
});

test("Settings ▸ New design also asks before leaving unsaved edits",async({page})=>{
 const {puts}=await setup(page);await ready(page,"&e2e=1");
 await page.waitForFunction(()=>typeof (window as any).__auraSetLayout==="function");
 await dirty(page);
 const newDesign=async()=>{await page.getByRole("button",{name:"Settings",exact:true}).click();await page.getByRole("menuitem",{name:/New design/}).click()};
 await newDesign();
 const guard=page.getByRole("dialog",{name:"Unsaved changes"});
 await expect(guard).toBeVisible();
 await guard.getByRole("button",{name:"Cancel",exact:true}).click();
 await expect(guard).toHaveCount(0);
 await expect(page.getByTestId("three-host")).toBeVisible();
 await expect(page).toHaveURL(/projectId=project-fan/);
 await newDesign();
 await guard.getByRole("button",{name:"Discard",exact:true}).click();
 await expect(page.getByRole("heading",{name:"What do you want to build?"})).toBeVisible();
 expect(puts).toHaveLength(0);
});

test("Shareable link is reachable by keyboard, announces its reason and does nothing",async({page})=>{
 await setup(page);await ready(page);
 await fileMenu(page).click();
 await page.getByRole("menuitem",{name:"Export",exact:true}).focus();
 await page.keyboard.press("ArrowRight");await page.keyboard.press("ArrowDown");
 const share=page.getByRole("menuitem",{name:"Shareable link"});
 await expect(share).toBeFocused();
 await expect(share).toHaveAccessibleDescription(REASON);
 await page.keyboard.press("Enter");
 await expect(page.getByRole("menu",{name:"Export"})).toBeVisible();
 await expect(share).toBeFocused();
});

test("the topbar project switcher and the AURA button also ask before leaving unsaved edits",async({page})=>{
 const {puts}=await setup(page);await ready(page,"&e2e=1");
 await page.waitForFunction(()=>typeof (window as any).__auraSetLayout==="function");
 await dirty(page);
 await page.getByRole("button",{name:/PROJECT/}).click();
 await page.getByTestId("projects-panel").getByRole("button",{name:/weather station/i}).click();
 const guard=page.getByRole("dialog",{name:"Unsaved changes"});
 await expect(guard).toBeVisible();
 await guard.getByRole("button",{name:"Cancel",exact:true}).click();
 await expect(page).toHaveURL(/projectId=project-fan/);
 await page.getByRole("button",{name:"AURA",exact:true}).click();
 await expect(guard).toBeVisible();
 await guard.getByRole("button",{name:"Cancel",exact:true}).click();
 await expect(page.getByTestId("three-host")).toBeVisible();
 await page.getByRole("button",{name:"AURA",exact:true}).click();
 await guard.getByRole("button",{name:"Discard",exact:true}).click();
 await expect(page.getByRole("heading",{name:"What do you want to build?"})).toBeVisible();
 expect(puts).toHaveLength(0);
});

test("the header shows Unsaved changes while the layout is dirty and Saved otherwise",async({page})=>{
 await setup(page);await ready(page,"&e2e=1");
 await page.waitForFunction(()=>typeof (window as any).__auraSetLayout==="function");
 const state=page.getByTestId("saved-state");
 await expect(state).toHaveText(/Saved/);await expect(state).not.toHaveText(/Unsaved/);
 await dirty(page);
 await expect(state).toHaveText(/Unsaved changes/);
 await expect(state).not.toHaveAttribute("aria-hidden","true");
 await page.keyboard.press("Control+s");
 await expect(state).toHaveText(/Saved/);await expect(state).not.toHaveText(/Unsaved/);
});

test("Cancel while the guard Save is still in flight never runs the pending action",async({page})=>{
 const {puts}=await setup(page);
 await page.route("**/api/projects/project-fan/layout",async route=>{
  if(route.request().method()==="PUT"){puts.push(route.request().postDataJSON());await new Promise(r=>setTimeout(r,800));return route.fulfill({json:{updatedAt:"2026-10-29T10:00:00Z"}})}
  return route.fulfill({json:{layout:emptyLayout,updatedAt:null}});
 });
 await ready(page,"&e2e=1");
 await page.waitForFunction(()=>typeof (window as any).__auraSetLayout==="function");
 await dirty(page);
 await page.keyboard.press("Control+o");
 await page.getByRole("dialog",{name:"Open project"}).getByRole("button",{name:/weather station/i}).click();
 const guard=page.getByRole("dialog",{name:"Unsaved changes"});
 await guard.getByRole("button",{name:"Save",exact:true}).click();
 await page.keyboard.press("Escape");
 await expect(guard).toHaveCount(0);
 await expect.poll(()=>puts.length).toBe(1);
 await page.waitForTimeout(1200);
 await expect(page).toHaveURL(/projectId=project-fan/);
});

test("Import works from the Code space too",async({page})=>{
 await setup(page);await ready(page);
 await page.getByTestId("space-toolbar").getByRole("button",{name:"Code",exact:true}).click();
 await expect(page.getByTestId("code-view")).toBeVisible();
 await fileMenu(page).click();await page.getByRole("menuitem",{name:"Import",exact:true}).hover();
 const [chooser]=await Promise.all([page.waitForEvent("filechooser"),page.getByRole("menuitem",{name:"Project ZIP…"}).click()]);
 expect(chooser).toBeTruthy();
});
