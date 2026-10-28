import {expect,test} from "@playwright/test";
import {mock} from "./fanFixture";

test.beforeEach(async({page})=>{await mock(page);await page.route("**/api/hardware/ports",r=>r.fulfill({json:{ports:[],toolchainMissing:null}}))});

test("application menu replaces the space tabs and its items run existing actions",async({page})=>{
 await page.goto("/?projectId=project-fan");
 const menubar=page.getByRole("navigation",{name:"Application menu"});
 for(const name of ["File","Edit","View","Project","Components","Tools","Help"])await expect(menubar.getByRole("button",{name,exact:true})).toBeVisible();
 const view=menubar.getByRole("button",{name:"View",exact:true});
 await view.click();await expect(view).toHaveAttribute("aria-expanded","true");
 await page.keyboard.press("Escape");await expect(view).toHaveAttribute("aria-expanded","false");await expect(view).toBeFocused();
 await view.click();await page.getByRole("menuitem",{name:"Wiring"}).click();
 await expect(page.getByTestId("schematic")).toBeVisible();
 await menubar.getByRole("button",{name:"Components",exact:true}).click();await page.mouse.click(5,600);
 await expect(page.getByRole("menu")).toHaveCount(0);
 await menubar.getByRole("button",{name:"Components",exact:true}).click();await page.getByRole("menuitem",{name:"Component library"}).click();
 await expect(page.getByRole("button",{name:"Open component library"})).toHaveAttribute("aria-expanded","true");
});

test("spaces sit in the toolbar above the viewport with the assembly select and concept badge",async({page})=>{
 await page.goto("/?projectId=project-fan");
 const toolbar=page.getByTestId("space-toolbar");
 await expect(toolbar.getByRole("navigation",{name:"Workspace spaces"})).toBeVisible();
 await expect(toolbar.getByLabel("Assembly")).toBeVisible();await expect(toolbar.getByTestId("concept-badge")).toBeVisible();
 await toolbar.getByRole("button",{name:"Code",exact:true}).click();await expect(page.getByTestId("code-view")).toBeVisible();
 await toolbar.getByRole("button",{name:"Design",exact:true}).click();await expect(page.getByTestId("three-host")).toBeVisible();
});

test("view FAB expands Fit, Explode, Solid and Show all, and collapses on click, outside click and Escape",async({page})=>{
 await page.goto("/?projectId=project-fan");
 const fab=page.getByRole("button",{name:"View controls"});
 await expect(fab).toHaveAttribute("aria-expanded","false");await expect(page.getByRole("button",{name:"Explode"})).toHaveCount(0);
 await fab.click();
 for(const name of ["Fit","Explode","Solid","Show all"])await expect(page.getByRole("button",{name,exact:true})).toBeVisible();
 await fab.click();await expect(fab).toHaveAttribute("aria-expanded","false");
 await fab.click();await page.mouse.click(5,600);await expect(fab).toHaveAttribute("aria-expanded","false");
 await fab.focus();await page.keyboard.press("Enter");await expect(fab).toHaveAttribute("aria-expanded","true");
 await page.keyboard.press("Escape");await expect(fab).toHaveAttribute("aria-expanded","false");await expect(fab).toBeFocused();
 await fab.click();await page.getByRole("button",{name:"Explode",exact:true}).click();
 await expect(page.getByRole("button",{name:"Assemble",exact:true})).toBeVisible();
});

for(const width of [1280,900])test(`no horizontal overflow at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:860});await page.goto("/?projectId=project-fan");
 await expect(page.getByTestId("space-toolbar")).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
 const box=await page.getByTestId("space-toolbar").boundingBox(),fab=await page.getByRole("button",{name:"View controls"}).boundingBox();
 expect(fab!.y).toBeGreaterThan(box!.y+box!.height-1);
});

const covered=async(page:any,locator:any)=>{const box=await locator.boundingBox();return page.evaluate(([x,y,el]:any)=>{const hit=document.elementFromPoint(x,y);return !(el===hit||el.contains(hit))},[box.x+box.width/2,box.y+box.height/2,await locator.elementHandle()])};

for(const width of [1280,1000])test(`the open view FAB never covers the view switch or library toggle at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:860});await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"View controls"}).click();
 expect(await covered(page,page.getByRole("button",{name:"Open component library"}))).toBe(false);
 await page.getByRole("button",{name:"View controls"}).click();
 await page.getByRole("button",{name:"Wiring",exact:true}).click();await page.getByRole("button",{name:"View controls"}).click();
 expect(await covered(page,page.getByRole("group",{name:"Design view"}).getByRole("button",{name:"3D view"}))).toBe(false);
});

test("phone width keeps the menu off the space toolbar",async({page})=>{
 await page.setViewportSize({width:390,height:820});await page.goto("/?projectId=project-fan");
 expect(await covered(page,page.getByTestId("space-toolbar").getByRole("button",{name:"Simulation",exact:true}))).toBe(false);
 expect(await covered(page,page.getByTestId("space-toolbar").getByRole("button",{name:"Code",exact:true}))).toBe(false);
});

for(const width of [920,1280])test(`status and routing notes stay readable and clear of the view switch at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:860});await page.goto("/?projectId=project-fan");
 const note=await page.locator(".narration-card").boundingBox(),sw=await page.getByRole("group",{name:"Design view"}).boundingBox();
 // Where the viewport is too narrow for both, the status note is hidden rather than squeezed.
 if(!note)return;
 expect(note.width).toBeGreaterThan(200);
 expect(note.y+note.height<=sw!.y||note.x+note.width<=sw!.x).toBe(true);
});

test("keyboard focus survives FAB toggles and menu selections",async({page})=>{
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"View controls"}).click();
 await page.getByRole("button",{name:"Explode",exact:true}).focus();await page.keyboard.press("Enter");
 await expect(page.getByRole("button",{name:"Assemble",exact:true})).toBeFocused();
 const file=page.getByRole("navigation",{name:"Application menu"}).getByRole("button",{name:"File",exact:true});
 await file.click();await page.getByRole("menuitem",{name:"Switch project"}).click();
 await expect(file).toBeFocused();
});
