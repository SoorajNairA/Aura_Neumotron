import {expect,test} from "@playwright/test";
import {mock} from "./fanFixture";

test.beforeEach(async({page})=>{await mock(page);await page.route("**/api/hardware/ports",r=>r.fulfill({json:{ports:[],toolchainMissing:null}}))});

test("hamburger leads the menu bar and holds the view and tool actions",async({page})=>{
 await page.goto("/?projectId=project-fan");
 const menubar=page.getByRole("navigation",{name:"Application menu"});
 const buttons=menubar.getByRole("button");
 await expect(buttons.first()).toHaveAccessibleName("Open component library");
 await expect(buttons.first()).toHaveText(/☰/);
 const names=(await buttons.allInnerTexts()).map(text=>text.replace(/[⌄\s]+$/,"").trim());
 expect(names).toEqual(["☰","File","Edit","Project","Help"]);
 for(const name of ["View","Components","Tools"])await expect(menubar.getByRole("button",{name,exact:true})).toHaveCount(0);
 const burger=buttons.first();
 await burger.click();await expect(burger).toHaveAttribute("aria-expanded","true");
 const items=await page.getByRole("menu").locator("[role^=menuitem]").allInnerTexts();
 expect(items.map(text=>text.split("\n")[0].trim())).toEqual(["Component library","Fit","Explode","Solid","Show all","Developer panel","Model settings","Code and compile","Connect device"]);
 await page.keyboard.press("Escape");await expect(burger).toHaveAttribute("aria-expanded","false");await expect(burger).toBeFocused();
 await burger.click();await page.getByRole("menuitem",{name:"Explode",exact:true}).click();
 await burger.click();await expect(page.getByRole("menuitem",{name:"Assemble",exact:true})).toBeVisible();
 await page.keyboard.press("Escape");
 await page.getByRole("group",{name:"Design view"}).getByRole("button",{name:"Wiring",exact:true}).click();
 await expect(page.getByTestId("schematic")).toBeVisible();
 await menubar.getByRole("button",{name:"File",exact:true}).click();await page.mouse.click(5,600);
 await expect(page.getByRole("menu")).toHaveCount(0);
});

test("the Component library item is a checkbox that toggles the library panel",async({page})=>{
 await page.route("**/api/catalogue",r=>r.fulfill({json:[]}));
 await page.goto("/?projectId=project-fan");
 const burger=page.getByRole("button",{name:"Open component library"});
 await burger.click();
 const item=page.getByRole("menuitemcheckbox",{name:"Component library"});
 await expect(item).toHaveAttribute("aria-checked","false");
 await item.click();
 await expect(page.getByRole("dialog",{name:"Component library"})).toBeVisible();
 await burger.click();await expect(item).toHaveAttribute("aria-checked","true");
 await page.keyboard.press("ArrowDown");await page.keyboard.press("ArrowUp");await expect(item).toBeFocused();
 await item.click();
 await expect(page.getByRole("dialog",{name:"Component library"})).toHaveCount(0);
 await burger.click();await expect(item).toHaveAttribute("aria-checked","false");
});

test("the view switch sits at the top-left of the viewport and the old status card is gone",async({page})=>{
 await page.goto("/?projectId=project-fan");
 await expect(page.getByTestId("three-host")).toBeVisible();
 for(const view of ["3D view","Wiring","Split"]){
  await page.getByRole("group",{name:"Design view"}).getByRole("button",{name:view,exact:true}).click();
  const box=await page.getByRole("group",{name:"Design view"}).boundingBox(),vp=await page.locator(".viewport").boundingBox();
  expect(box!.x-vp!.x).toBeLessThan(80);expect(box!.y-vp!.y).toBeLessThan(80);
  expect(await page.locator(".viewport").evaluate((node,el)=>node.contains(el),await page.getByRole("group",{name:"Design view"}).elementHandle())).toBe(true);
 }
 await expect(page.locator(".narration-card")).toHaveCount(0);
});

test("narration shows as a dismissible toast that clears itself",async({page})=>{
 await page.route("**/api/projects/project-fan/narrations",r=>r.fulfill({json:[{narrationId:"n1",text:"Routing the fan supply through the driver."}]}));
 await page.goto("/?projectId=project-fan");
 const toast=page.getByRole("status").filter({hasText:"Routing the fan supply"});
 await expect(toast).toBeVisible();
 await toast.getByRole("button",{name:"Dismiss notification",exact:true}).click();await expect(toast).toHaveCount(0);
 await page.reload();await expect(toast).toBeVisible();
 await expect(toast).toHaveCount(0,{timeout:6500});
});

test("the toast stays clear of the view switch, FAB and composer",async({page})=>{
 await page.route("**/api/projects/project-fan/narrations",r=>r.fulfill({json:[{narrationId:"n1",text:"Routing the fan supply through the driver."}]}));
 await page.goto("/?projectId=project-fan");
 const toast=page.getByRole("status").filter({hasText:"Routing the fan supply"});await expect(toast).toBeVisible();
 const t=(await toast.boundingBox())!,vp=(await page.locator(".viewport").boundingBox())!;
 expect(t.x).toBeLessThan(vp.x+60);expect(t.y+t.height).toBeGreaterThan(vp.y+vp.height-120);
 const apart=(a:any,b:any)=>a.x+a.width<=b.x||b.x+b.width<=a.x||a.y+a.height<=b.y||b.y+b.height<=a.y;
 for(const other of [page.getByRole("group",{name:"Design view"}),page.getByRole("button",{name:"View controls"}),page.locator(".command.dock")])expect(apart(t,(await other.boundingBox())!)).toBe(true);
});

test("sidebars run to the bottom of the window and scroll their own content",async({page})=>{
 await page.goto("/?projectId=project-fan");
 const height=await page.evaluate(()=>window.innerHeight);
 for(const [outer,inner] of [[".systems-rail",".rail-content"],[".contextual-inspector",".inspector-content"]]){
  const box=(await page.locator(outer).boundingBox())!;expect(Math.abs(box.y+box.height-height)).toBeLessThanOrEqual(2);
  expect(await page.locator(inner).evaluate(node=>getComputedStyle(node).overflowY)).toBe("auto");
 }
 const dock=(await page.locator(".command.dock").boundingBox())!,rail=(await page.locator(".systems-rail").boundingBox())!;
 expect(dock.x).toBeGreaterThanOrEqual(rail.x+rail.width-1);
});

test("File > New design shows a clean welcome screen",async({page})=>{
 await page.goto("/?projectId=project-fan");
 await expect(page.getByTestId("three-host")).toBeVisible();
 await page.getByRole("navigation",{name:"Application menu"}).getByRole("button",{name:"File",exact:true}).click();
 await page.getByRole("menuitem",{name:"New design"}).click();
 await expect(page.getByRole("heading",{name:"What do you want to build?"})).toBeVisible();
 await expect(page.getByText(/BUILDING/i)).toHaveCount(0);
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

test("keyboard focus survives FAB toggles and menu selections",async({page})=>{
 await page.goto("/?projectId=project-fan");
 await page.getByRole("button",{name:"View controls"}).click();
 await page.getByRole("button",{name:"Explode",exact:true}).focus();await page.keyboard.press("Enter");
 await expect(page.getByRole("button",{name:"Assemble",exact:true})).toBeFocused();
 const file=page.getByRole("navigation",{name:"Application menu"}).getByRole("button",{name:"File",exact:true});
 await file.click();await page.getByRole("menuitem",{name:"Switch project"}).click();
 await expect(file).toBeFocused();
});
