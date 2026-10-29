import {expect,Page,test} from "@playwright/test";
import {graph,mock,project} from "./fanFixture";
import circuit from "./wiringCircuit.json" with {type:"json"};

// All endpoints are mocked; AURA_E2E_MOCK_ONLY=1 needs no backend. The circuit is a generated desk-fan schematic.
const FAN="schematic_component_2",CONTROLLER="schematic_component_0",TRACE="schematic_trace_2";
const WIRE="net-ground-63260bbf670d:M1.GND|U1.GND";
const empty={parts:{},wires:{},labels:{}};
test.use({viewport:{width:1600,height:1000}});
const withSchematic={...project,representations:[{type:"circuit_schematic",artifactId:"wiring"}]};

async function setup(page:Page,stored:any=empty){
 await mock(page);
 await page.route("**/api/hardware/ports",r=>r.fulfill({json:{ports:[],toolchainMissing:null}}));
 await page.route("**/api/catalogue",r=>r.fulfill({json:[]}));
 await page.route("**/api/projects",r=>r.fulfill({json:[withSchematic]}));
 await page.route("**/api/projects/project-fan",r=>r.fulfill({json:withSchematic}));
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:{...graph,entities:[...graph.entities,{id:"net-control-87ea5b048247",kind:"net",name:"control",metadata:{semantic_type:"electrical_net",role:"control",terminals:[]}}]}}));
 await page.route("**/api/artifacts/wiring/content",r=>r.fulfill({json:circuit}));
 const state={stored,puts:[] as {at:number;body:any}[]};
 await page.route("**/api/projects/project-fan/layout",async route=>{
  if(route.request().method()==="PUT"){const body=route.request().postDataJSON();state.puts.push({at:Date.now(),body});state.stored=body.layout;return route.fulfill({json:{updatedAt:"2026-10-29T10:00:00Z"}})}
  return route.fulfill({json:{layout:state.stored,updatedAt:null}});
 });
 return state;
}
async function openWiring(page:Page){
 await page.goto("/?projectId=project-fan");
 await expect(page.getByTestId("three-host")).toBeVisible();
 await page.getByRole("button",{name:"Wiring",exact:true}).click();
 await expect(part(page,FAN)).toBeVisible();
 // Notifications can sit over the drawing; close any that is open.
 const dismiss=page.getByRole("button",{name:"Dismiss notification"});
 if(await dismiss.isVisible())await dismiss.click();
}
const camera=(page:Page)=>page.getByTestId("schematic-camera");
const drawing=(page:Page)=>camera(page).locator("svg[data-real-to-screen-transform]");
const part=(page:Page,id:string)=>camera(page).locator(`svg g[data-schematic-component-id="${id}"]`).first();
const center=async(page:Page,id:string)=>{const box=(await part(page,id).boundingBox())!;return {x:box.x+box.width/2,y:box.y+box.height/2,w:box.width}};
async function drag(page:Page,from:{x:number;y:number},dx:number,dy:number){
 await page.mouse.move(from.x,from.y);await page.mouse.down();
 for(let i=1;i<=6;i++)await page.mouse.move(from.x+dx*i/6,from.y+dy*i/6);
 await page.mouse.up();
}
// Screen point halfway along the rendered trace path.
const traceMidpoint=(page:Page,id:string)=>page.evaluate(id=>{
 const path=document.querySelector(`[data-testid=schematic-camera] g.trace[data-schematic-trace-id="${id}"] path`) as SVGPathElement;
 const point=path.getPointAtLength(path.getTotalLength()*.5).matrixTransform(path.getScreenCTM()!);
 return {x:point.x,y:point.y};
},id);
// Fan position relative to the controller, in controller widths (independent of zoom and fit).
const relative=async(page:Page)=>{const fan=await center(page,FAN),controller=await center(page,CONTROLLER);return {x:(fan.x-controller.x)/controller.w,y:(fan.y-controller.y)/controller.w}};

test("Select and Pan are a pressed-state toggle with Undo and Redo",async({page})=>{
 await setup(page);await openWiring(page);
 const tools=page.getByRole("toolbar",{name:"Wiring tools"});
 await expect(tools.getByRole("button",{name:"Select"})).toHaveAttribute("aria-pressed","true");
 await expect(tools.getByRole("button",{name:"Pan"})).toHaveAttribute("aria-pressed","false");
 await expect(tools.getByRole("button",{name:"Undo"})).toBeDisabled();
 await expect(tools.getByRole("button",{name:"Redo"})).toBeDisabled();
 await tools.getByRole("button",{name:"Pan"}).click();
 await expect(tools.getByRole("button",{name:"Pan"})).toHaveAttribute("aria-pressed","true");
 await expect(tools.getByRole("button",{name:"Select"})).toHaveAttribute("aria-pressed","false");
});

test("dragging a part in Select moves it under the pointer, not the camera, and autosaves about 1 s later",async({page})=>{
 const state=await setup(page);await openWiring(page);
 const cameraBefore=await camera(page).getAttribute("data-camera");
 const before=await center(page,FAN),controller=await center(page,CONTROLLER);
 await drag(page,before,80,-50);
 const edited=Date.now();
 await expect.poll(async()=>(await center(page,FAN)).x-before.x).toBeGreaterThan(70);
 const after=await center(page,FAN);
 // The part follows the pointer in both axes (sign and scale of the screen → circuit conversion).
 expect(Math.abs(after.x-before.x-80)).toBeLessThan(10);
 expect(Math.abs(after.y-before.y+50)).toBeLessThan(10);
 // Other parts stay put and the camera is untouched.
 const still=await center(page,CONTROLLER);
 expect(Math.abs(still.x-controller.x)).toBeLessThan(2);expect(Math.abs(still.y-controller.y)).toBeLessThan(2);
 expect(await camera(page).getAttribute("data-camera")).toBe(cameraBefore);
 await expect(page.getByTestId("saved-state")).toHaveText(/Unsaved changes/);
 await expect.poll(()=>state.puts.length,{timeout:3000}).toBe(1);
 const delay=state.puts[0].at-edited;
 expect(delay).toBeGreaterThan(700);expect(delay).toBeLessThanOrEqual(1500);
 const offset=state.puts[0].body.layout.parts["component-fan"];
 expect(offset.dx).toBeGreaterThan(0);expect(offset.dy).toBeGreaterThan(0);// circuit y points up
 await expect(page.getByTestId("saved-state")).toHaveText(/Saved/);
});

test("the conversion holds when zoomed in",async({page})=>{
 await setup(page);await openWiring(page);
 await page.getByRole("button",{name:"+",exact:true}).click();await page.getByRole("button",{name:"+",exact:true}).click();
 const before=await center(page,FAN),zoomed=await camera(page).getAttribute("data-camera");
 await drag(page,before,-60,40);
 expect(await camera(page).getAttribute("data-camera")).toBe(zoomed);
 await expect.poll(async()=>(await center(page,FAN)).x-before.x).toBeLessThan(-50);
 const after=await center(page,FAN);
 expect(Math.abs(after.x-before.x+60)).toBeLessThan(12);expect(Math.abs(after.y-before.y-40)).toBeLessThan(12);
});

test("Pan drags the camera, not the part; Space-drag pans in Select mode",async({page})=>{
 const state=await setup(page);await openWiring(page);
 const svg=drawing(page);
 const offset=async()=>{const fan=await center(page,FAN),box=(await svg.boundingBox())!;return {x:fan.x-box.x,y:fan.y-box.y}};
 const before=await offset(),cameraBefore=await camera(page).getAttribute("data-camera");
 await page.getByRole("button",{name:"Pan",exact:true}).click();
 await drag(page,await center(page,FAN),70,30);
 await expect(camera(page)).not.toHaveAttribute("data-camera",cameraBefore!);
 const after=await offset();
 expect(Math.abs(after.x-before.x)).toBeLessThan(2);expect(Math.abs(after.y-before.y)).toBeLessThan(2);
 await page.getByRole("button",{name:"Select",exact:true}).click();
 const panned=await camera(page).getAttribute("data-camera");
 await camera(page).focus();await page.keyboard.down("Space");
 await drag(page,await center(page,FAN),-40,0);
 await page.keyboard.up("Space");
 await expect(camera(page)).not.toHaveAttribute("data-camera",panned!);
 expect(Math.abs((await offset()).x-before.x)).toBeLessThan(2);
 await page.waitForTimeout(1300);
 expect(state.puts).toHaveLength(0);
});

test("selecting a wire shows segment handles and dragging one moves that segment",async({page})=>{
 const state=await setup(page);await openWiring(page);
 await expect(page.getByTestId("bend-handle")).toHaveCount(0);
 const mid=await traceMidpoint(page,TRACE);
 await page.mouse.click(mid.x,mid.y);
 const handles=page.getByTestId("bend-handle");
 await expect(handles).toHaveCount(5);
 await expect(handles.nth(2)).toHaveAttribute("data-orientation","horizontal");
 await expect(handles.nth(2)).toHaveAccessibleName(`Bend segment 3 of wire ${WIRE}`);
 const box=(await handles.nth(2).boundingBox())!,from={x:box.x+box.width/2,y:box.y+box.height/2};
 await drag(page,from,0,40);
 await expect.poll(async()=>{const b=(await handles.nth(2).boundingBox())!;return b.y+b.height/2-from.y}).toBeGreaterThan(30);
 const moved=(await handles.nth(2).boundingBox())!;
 expect(Math.abs(moved.x+moved.width/2-from.x)).toBeLessThan(3);
 await expect.poll(()=>state.puts.length,{timeout:3000}).toBe(1);
 const bends=state.puts[0].body.layout.wires[WIRE];
 expect(bends[2]).toBeLessThan(0);
 expect(bends.filter((value:number,i:number)=>i!==2&&value!==0)).toEqual([]);
 // Keyboard: a focused handle moves with the arrow keys.
 await handles.nth(2).focus();await page.keyboard.press("ArrowUp");
 await expect.poll(()=>state.puts.length,{timeout:3000}).toBe(2);
 expect(state.puts[1].body.layout.wires[WIRE][2]).toBeCloseTo(bends[2]+.1,5);
});

test("renaming in the inspector shows in the schematic, the component list and the inspector title; undo and redo work",async({page})=>{
 const state=await setup(page);await openWiring(page);
 await part(page,FAN).click();
 const field=page.getByTestId("part-info").getByRole("textbox",{name:"Display name"});
 await expect(field).toHaveValue("Desk fan");
 await field.fill("Cooling fan");await field.press("Enter");
 await expect(drawing(page)).toContainText("Cooling fan");
 await expect(page.getByTestId("part-info").getByRole("heading",{level:2})).toHaveText("Cooling fan");
 await expect(page.getByRole("button",{name:"Cooling fan component-fan"})).toBeVisible();
 await expect.poll(()=>state.puts.length,{timeout:3000}).toBe(1);
 expect(state.puts[0].body.layout.labels).toEqual({"component-fan":"Cooling fan"});
 // Undo/redo in the wiring view.
 await camera(page).focus();
 await page.keyboard.press("Control+z");
 await expect(drawing(page)).toContainText("Desk fan");
 await expect(drawing(page)).not.toContainText("Cooling fan");
 await expect(page.getByTestId("part-info").getByRole("heading",{level:2})).toHaveText("Desk fan");
 await page.keyboard.press("Control+Shift+z");
 await expect(drawing(page)).toContainText("Cooling fan");
 await page.keyboard.press("Control+z");await page.keyboard.press("Control+y");
 await expect(drawing(page)).toContainText("Cooling fan");
 await expect(page.getByRole("toolbar",{name:"Wiring tools"}).getByRole("button",{name:"Undo"})).toBeEnabled();
});

test("Ctrl+Z undoes a part move and Ctrl+Shift+Z redoes it",async({page})=>{
 await setup(page);await openWiring(page);
 const before=await center(page,FAN);
 await drag(page,before,60,0);
 await expect.poll(async()=>(await center(page,FAN)).x-before.x).toBeGreaterThan(50);
 await page.keyboard.press("Control+z");
 await expect.poll(async()=>Math.abs((await center(page,FAN)).x-before.x)).toBeLessThan(2);
 await page.keyboard.press("Control+Shift+z");
 await expect.poll(async()=>(await center(page,FAN)).x-before.x).toBeGreaterThan(50);
});

test("a net display name shows on the net button and the net inspector",async({page})=>{
 await setup(page);await openWiring(page);
 await page.locator('.schematic-nets [data-net-id="net-control-87ea5b048247"]').click();
 const field=page.getByTestId("net-info").getByRole("textbox",{name:"Display name"});
 await field.fill("Fan PWM");await field.press("Enter");
 await expect(page.getByTestId("net-info").getByRole("heading",{level:2})).toHaveText("Fan PWM");
 await expect(page.locator('.schematic-nets [data-net-id="net-control-87ea5b048247"]')).toHaveText("Fan PWM");
});

test("reload restores part positions, wire bends and labels from the saved layout",async({page})=>{
 await setup(page);await openWiring(page);
 const base=await relative(page);
 const baseTrace=await page.evaluate(id=>document.querySelector(`g.trace[data-schematic-trace-id="${id}"] path`)!.getAttribute("d"),TRACE);
 const stored={parts:{"component-fan":{dx:1.5,dy:0}},wires:{[WIRE]:[0,0,-.6]},labels:{"component-fan":"Stored fan"}};
 const page2=await page.context().newPage();
 await setup(page2,stored);await openWiring(page2);
 await expect(drawing(page2)).toContainText("Stored fan");
 const moved=await relative(page2);
 expect(moved.x-base.x).toBeGreaterThan(.5);
 const bentTrace=await page2.evaluate(id=>document.querySelector(`g.trace[data-schematic-trace-id="${id}"] path`)!.getAttribute("d"),TRACE);
 expect(bentTrace).not.toBe(baseTrace);
 // Saved bends come back as the same handles.
 const mid2=await traceMidpoint(page2,TRACE);
 await page2.mouse.click(mid2.x,mid2.y);
 await expect(page2.getByTestId("bend-handle")).toHaveCount(5);
});

test("a drag then reload keeps the position",async({page})=>{
 const state=await setup(page);await openWiring(page);
 await drag(page,await center(page,FAN),70,0);
 await expect.poll(()=>state.puts.length,{timeout:3000}).toBe(1);
 const before=await relative(page);
 await page.reload();
 await page.getByRole("button",{name:"Wiring",exact:true}).click();
 await expect(part(page,FAN)).toBeVisible();
 await expect.poll(async()=>Math.abs((await relative(page)).x-before.x)).toBeLessThan(.05);
});
