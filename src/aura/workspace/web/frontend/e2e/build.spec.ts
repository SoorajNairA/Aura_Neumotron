import {expect,test,Page} from "@playwright/test";
import {mock,supported} from "./fanFixture";

const ports={ports:[{address:"COM1",label:"COM1",protocol:"serial",vid:null,pid:null,likelyEsp32:false,fake:false},
 {address:"COM5",label:"COM5",protocol:"serial",vid:"10C4",pid:"EA60",likelyEsp32:true,fake:false}],toolchainMissing:null};
const line=(seq:number,rev:string,t:number,fan:number)=>({seq,time:`2026-10-28T14:02:0${seq}+00:00`,text:JSON.stringify({t_c:t,fan,rev}),telemetry:{t_c:t,fan,rev}});

async function hardware(page:Page,serial:()=>any,firmware:any=supported){
 await mock(page,firmware);
 await page.route("**/api/hardware/ports",r=>r.fulfill({json:ports}));
 await page.route("**/api/projects/project-fan/serial?*",r=>r.fulfill({json:serial()}));
 await page.route("**/api/projects/project-fan/serial/start",r=>r.fulfill({json:{running:true,port:"COM5",fake:false}}));
 await page.route("**/api/projects/project-fan/serial/stop",r=>r.fulfill({json:{running:false}}));
}
const idle={running:false,port:null,fake:false,lines:[],wrongRevision:null,evidence:null};

test("Build space lists ports, confirms before writing, and reports the upload honestly",async({page})=>{
 await hardware(page,()=>idle);
 let uploads=0;
 await page.route("**/api/projects/project-fan/firmware/upload",r=>{uploads++;r.fulfill(uploads===1
  ?{status:409,json:{detail:{code:"COMPILE_REQUIRED",message:"Compile this revision first."}}}
  :{json:{status:"uploaded",port:"COM5",revisionId:"revision-1",uploadedAt:"2026-10-28T14:00:00+00:00",errors:[],rawOutput:"",fake:false,hint:null}})});
 await page.goto("/?projectId=project-fan");await page.getByRole("button",{name:"Build",exact:true}).click();
 await expect(page.getByTestId("port-select")).toHaveValue("COM5");
 await expect(page.getByTestId("port-select").locator("option:checked")).toHaveText("COM5 — likely ESP32 (unverified)");
 await expect(page.getByTestId("hardware-evidence")).toHaveText("Not tried on hardware");
 await page.getByRole("button",{name:"UPLOAD"}).click();
 await expect(page.getByTestId("upload-confirm")).toContainText("This writes the firmware to the board on COM5.");
 expect(uploads).toBe(0);
 await page.getByRole("button",{name:"Write to board"}).click();
 await expect(page.getByTestId("upload-status")).toHaveText("Compile this revision first.");
 await page.getByRole("button",{name:"UPLOAD"}).click();await page.getByRole("button",{name:"Write to board"}).click();
 await expect(page.getByTestId("upload-status")).toHaveText("Uploaded revision revision-1 to COM5 at 2026-10-28 14:00 UTC — not yet observed running");
});

test("serial monitor shows the log, a wrong-revision banner, and hardware evidence only from real telemetry",async({page})=>{
 let state:any=idle;
 await hardware(page,()=>state);
 await page.goto("/?projectId=project-fan");await page.getByRole("button",{name:"Build",exact:true}).click();
 state={...idle,running:true,port:"COM5",lines:[{seq:1,time:"2026-10-28T14:02:00+00:00",text:"ets Jun  8 2016 rst:0x1",telemetry:null},line(2,"revision-0",21,0)],wrongRevision:{board:"revision-0",current:"revision-1"}};
 await page.getByRole("button",{name:"Start monitor"}).click();
 await expect(page.getByTestId("serial-log")).toContainText("ets Jun  8 2016");
 await expect(page.getByTestId("wrong-revision")).toHaveText("Board runs revision revision-0, not the current design (revision-1). Upload to update it.");
 await expect(page.getByTestId("hardware-evidence")).toHaveText("Not tried on hardware");
 await expect(page.getByRole("button",{name:"UPLOAD"})).toBeDisabled();
 state={...state,lines:[line(3,"revision-1",22,0),line(4,"revision-1",22,0),line(5,"revision-1",23,0)],wrongRevision:null,
  evidence:{port:"COM5",revisionId:"revision-1",lines:3,firstSeen:"2026-10-28T14:02:03+00:00",agreement:"not checked"}};
 await expect(page.getByTestId("hardware-evidence")).toHaveText("Observed on hardware: COM5, revision revision-1, 3 lines, 2026-10-28 14:02 UTC");
 await expect(page.getByTestId("wrong-revision")).toHaveCount(0);
});

test("a fake board run is never shown as hardware evidence",async({page})=>{
 await hardware(page,()=>({...idle,running:true,port:"FAKE0",fake:true,lines:[line(1,"revision-1",21,0)],
  evidence:{port:"COM5",revisionId:"revision-1",lines:9,firstSeen:"2026-10-28T10:00:00+00:00",agreement:"not checked"}}));
 await page.goto("/?projectId=project-fan");await page.getByRole("button",{name:"Build",exact:true}).click();
 await expect(page.getByTestId("hardware-evidence")).toHaveText("Fake board (test) — not hardware evidence");
});
