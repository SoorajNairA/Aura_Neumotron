import {expect,test,Page} from "@playwright/test";

const SECRET="sk-e2e-secret-0123456789";
const rows:[string,string,string][]=[["component-controller","ESP32 DevKit","electronics"],["component-fan","Desk fan","actuator"]];
const parts=rows.map(([semanticId,label,subsystem],i)=>({semanticId,label,family:semanticId==="component-fan"?"fan":"microcontroller_board",subsystem,parentAssembly:"desk-fan",representationSource:"conceptual procedural model",dimensions:[60,30,60],assembledTransform:{position:[i*80,0,20]},explodedTransform:{position:[i*90,0,40]},verificationState:"estimated"}));
const project={projectId:"project-fan",objective:"Design a temperature-controlled desk fan",revision:1,status:"ready",planningMode:"live_model",assessment:{planningOrigin:{provider:"nebius",model:"nvidia/nemotron-3-super-120b-a12b",planningMode:"live_model"}},capability:{status:"SUPPORTED",reasons:[]},representations:[]};
const graph={project_id:"project-fan",entities:[{id:"project-fan",kind:"project",name:"Desk fan"},...parts.map(p=>({id:p.semanticId,kind:"component",name:p.label,parent_id:`subsystem-${p.subsystem}`,metadata:{}}))],relationships:[]};
const unsupported={supported:false,reasons:["Not part of this test"]};

type Profile={profileId:string;label:string;kind:string;baseUrl:string;model:string;hasKey:boolean;builtIn?:boolean};
// Stateful stand-in for the model-profile API. It never stores or returns a key, mirroring the real contract.
async function mock(page:Page){
 const state={active:null as string|null,profiles:[{profileId:"nemotron-nebius",label:"Nemotron on Nebius",kind:"nebius",baseUrl:"https://api.tokenfactory.nebius.com/v1/",model:"nvidia/nemotron-3-super-120b-a12b",hasKey:true,builtIn:true}] as Profile[],keyBodies:[] as string[],puts:[] as any[]};
 const payload=()=>({active:state.active,activeSource:state.active?"profile":"environment",environmentProvider:"nebius",profiles:state.profiles});
 await page.route("**/api/projects",r=>r.fulfill({json:[project]}));
 await page.route("**/api/projects/project-fan",r=>r.fulfill({json:project}));
 await page.route("**/api/projects/project-fan/revisions",r=>r.fulfill({json:[{revision:1,summary:"Project created"}]}));
 await page.route("**/api/projects/project-fan/assembly",r=>r.fulfill({json:{parts,connectors:[],relationships:[]}}));
 await page.route("**/api/projects/project-fan/graph",r=>r.fulfill({json:graph}));
 await page.route("**/api/projects/project-fan/verification",r=>r.fulfill({json:{state:"pass",summary:{},findings:[]}}));
 await page.route("**/api/projects/project-fan/work",r=>r.fulfill({json:{items:[]}}));
 await page.route("**/api/projects/project-fan/narrations",r=>r.fulfill({json:[]}));
 await page.route("**/api/projects/project-fan/firmware",r=>r.fulfill({json:unsupported}));
 await page.route("**/api/model-profiles",r=>r.fulfill({json:payload()}));
 await page.route("**/api/model-profiles/active",r=>{state.active=r.request().postDataJSON().profileId;return r.fulfill({json:payload()})});
 await page.route("**/api/model-profiles/*/key",r=>{state.keyBodies.push(r.request().postData()||"");const id=r.request().url().split("/").slice(-2)[0];const profile=state.profiles.find(p=>p.profileId===id);if(profile)profile.hasKey=true;return r.fulfill({status:204,body:""})});
 await page.route("**/api/model-profiles/*/test",r=>r.fulfill({json:{ok:false,code:"MODEL_AUTHENTICATION",message:"openai_compatible API key was rejected (401); check the key and model access"}}));
 await page.route(/\/api\/model-profiles\/[^/]+$/,r=>{
  const request=r.request(),id=request.url().split("/").pop()!;
  if(id==="active")return r.fallback();
  if(request.method()==="DELETE"){state.profiles=state.profiles.filter(p=>p.profileId!==id);if(state.active===id)state.active=null;return r.fulfill({status:204,body:""})}
  const body=request.postDataJSON();state.puts.push(body);
  if(body.baseUrl.startsWith("http://")&&!/localhost|127\.0\.0\.1/.test(body.baseUrl))return r.fulfill({status:422,json:{detail:{code:"PROFILE_INVALID",message:"invalid",errors:["baseUrl must use https unless it points to localhost or 127.0.0.1"]}}});
  const saved:Profile={profileId:id,label:body.label,kind:body.kind,baseUrl:body.baseUrl,model:body.model,hasKey:state.profiles.find(p=>p.profileId===id)?.hasKey||false};
  state.profiles=[...state.profiles.filter(p=>p.profileId!==id),saved];return r.fulfill({json:saved});
 });
 return state;
}

async function openSettings(page:Page){
 await page.getByRole("button",{name:"Settings"}).click();
 await page.getByRole("menuitem",{name:"Model settings"}).click();
 await expect(page.getByTestId("model-settings")).toBeVisible();
}

test("settings menu opens model settings; keys are write-only and cleared after save",async({page})=>{
 const state=await mock(page);await page.goto("/?projectId=project-fan");
 await expect(page.getByTestId("model-badge")).toHaveText("Nemotron · Nebius");
 await openSettings(page);
 await expect(page.getByTestId("model-env-note")).toContainText("environment");
 await expect(page.getByTestId("profile-nemotron-nebius")).toContainText("Key saved");
 const form=page.getByTestId("model-form");
 await form.getByLabel("Name").fill("Work OpenAI");
 await form.getByLabel("Base URL").fill("https://api.example.test/v1");
 await form.getByLabel("Model").fill("gpt-test");
 const key=form.getByLabel("API key");
 await expect(key).toHaveAttribute("type","password");
 await key.fill(SECRET);
 await form.getByRole("button",{name:"Save profile"}).click();
 await expect(page.getByTestId("model-form-notice")).toContainText("never shown again");
 await expect(key).toHaveValue("");
 const row=page.getByTestId("profile-work-openai");
 await expect(row).toContainText("Work OpenAI");await expect(row).toContainText("Key saved");
 expect(state.puts[0]).toMatchObject({label:"Work OpenAI",kind:"openai_compatible",baseUrl:"https://api.example.test/v1",model:"gpt-test"});
 expect(JSON.stringify(state.puts)).not.toContain(SECRET);
 expect(state.keyBodies).toEqual([JSON.stringify({key:SECRET})]);
 await expect(page.locator("body")).not.toContainText(SECRET);
 expect(await page.locator("input").evaluateAll(inputs=>inputs.map(input=>(input as HTMLInputElement).value))).not.toContain(SECRET);
});

test("connection test shows the real error text from the backend",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 await openSettings(page);
 await page.getByTestId("profile-nemotron-nebius").getByRole("button",{name:"Test"}).click();
 await expect(page.getByTestId("test-result-nemotron-nebius")).toHaveText("Authentication rejected: openai_compatible API key was rejected (401); check the key and model access");
});

test("invalid profile shows the validation error and nothing is added",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 await openSettings(page);
 const form=page.getByTestId("model-form");
 await form.getByLabel("Name").fill("Insecure");
 await form.getByLabel("Base URL").fill("http://api.example.test/v1");
 await form.getByLabel("Model").fill("gpt-test");
 await form.getByRole("button",{name:"Save profile"}).click();
 await expect(page.getByTestId("model-form-error")).toContainText("https");
 await expect(page.getByTestId("profile-insecure")).toHaveCount(0);
});

test("setting a profile active updates the badge menu and delete returns to the environment setting",async({page})=>{
 await mock(page);await page.goto("/?projectId=project-fan");
 await openSettings(page);
 const form=page.getByTestId("model-form");
 await form.getByLabel("Kind").selectOption("ollama_local");
 await form.getByLabel("Name").fill("Local llama");
 await form.getByLabel("Base URL").fill("http://localhost:11434");
 await form.getByLabel("Model").fill("llama3.1");
 await form.getByRole("button",{name:"Save profile"}).click();
 const row=page.getByTestId("profile-local-llama");
 await expect(row).toContainText("No key needed");
 await row.getByRole("button",{name:"Use"}).click();
 await expect(row.getByRole("button",{name:"In use"})).toBeDisabled();
 await expect(page.getByTestId("model-env-note")).toHaveCount(0);
 await page.getByRole("button",{name:"Close model settings"}).click();
 await page.getByTestId("model-badge").click();
 await expect(page.getByTestId("model-option-local-llama")).toContainText("✓ Local llama");
 await expect(page.getByTestId("model-option-nemotron-nebius")).not.toContainText("✓");
 await page.getByTestId("model-option-nemotron-nebius").click();
 await page.getByTestId("model-badge").click();
 await expect(page.getByTestId("model-option-nemotron-nebius")).toContainText("✓ Nemotron on Nebius");
 await page.getByRole("menuitem",{name:"Model settings…"}).click();
 await expect(page.getByTestId("model-settings")).toBeVisible();
 await page.getByTestId("profile-local-llama").getByRole("button",{name:"Delete"}).click();
 await expect(page.getByTestId("profile-local-llama")).toHaveCount(0);
});
