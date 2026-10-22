# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: round2-lifecycle.spec.ts >> real What-If isolates, applies one represented revision, and rejects stale candidate
- Location: e2e\round2-lifecycle.spec.ts:22:1

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: locator.click: Test timeout of 45000ms exceeded.
Call log:
  - waiting for getByTestId('scenario-info').getByRole('button', { name: 'DISCARD' })
    - locator resolved to <button>DISCARD</button>
  - attempting click action
    - waiting for element to be visible, enabled and stable
    - element is visible, enabled and stable
    - scrolling into view if needed
    - done scrolling
    - <b>SG90 Servo</b> from <section class="scenario-target">…</section> subtree intercepts pointer events
  - retrying click action
    - waiting for element to be visible, enabled and stable
    - element is visible, enabled and stable
    - scrolling into view if needed
    - done scrolling
    - <section class="scenario-target">…</section> intercepts pointer events
  - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <b>SG90 Servo</b> from <section class="scenario-target">…</section> subtree intercepts pointer events
    - retrying click action
      - waiting 100ms
    20 × waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <b>SG90 Servo</b> from <section class="scenario-target">…</section> subtree intercepts pointer events
     - retrying click action
       - waiting 500ms
       - waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <section class="scenario-target">…</section> intercepts pointer events
     - retrying click action
       - waiting 500ms
       - waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <b>SG90 Servo</b> from <section class="scenario-target">…</section> subtree intercepts pointer events
     - retrying click action
       - waiting 500ms
       - waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <b>SG90 Servo</b> from <section class="scenario-target">…</section> subtree intercepts pointer events
     - retrying click action
       - waiting 500ms
    - waiting for element to be visible, enabled and stable
    - element is visible, enabled and stable
    - scrolling into view if needed
    - done scrolling
    - <b>SG90 Servo</b> from <section class="scenario-target">…</section> subtree intercepts pointer events
  - retrying click action
    - waiting 500ms
    - waiting for element to be visible, enabled and stable
    - element is visible, enabled and stable
    - scrolling into view if needed
    - done scrolling
    - <section class="scenario-target">…</section> intercepts pointer events
  - retrying click action
    - waiting 500ms
    - waiting for element to be visible, enabled and stable
    - element is visible, enabled and stable
    - scrolling into view if needed
    - done scrolling
    - <b>SG90 Servo</b> from <section class="scenario-target">…</section> subtree intercepts pointer events
  - retrying click action
    - waiting 500ms

```

# Page snapshot

```yaml
- main [ref=e3]:
  - generic [ref=e4]:
    - button "AURA" [ref=e5] [cursor=pointer]:
      - generic [ref=e7]: ENGINEERING WORKSPACE
    - button "PROJECT Low Voltage Two Axis Robotic Arm With ▾" [ref=e8] [cursor=pointer]:
      - generic [ref=e9]: PROJECT
      - strong [ref=e10]: Low Voltage Two Axis Robotic Arm With
      - generic [ref=e11]: ▾
    - button "REV 01" [ref=e12] [cursor=pointer]
    - generic [ref=e13]: READY WITH LIMITATIONS
    - navigation "Workspace views" [ref=e14]:
      - button "ASSEMBLY" [ref=e15] [cursor=pointer]
      - button "SCHEMATIC" [ref=e16] [cursor=pointer]
      - button "SPLIT" [ref=e17] [cursor=pointer]
      - button "WORK" [ref=e18] [cursor=pointer]
    - button "VERIFICATION PASS · 0 FAILED" [ref=e19] [cursor=pointer]:
      - generic [ref=e20]: VERIFICATION
      - generic [ref=e21]: PASS · 0 FAILED
    - generic "Backend connection" [ref=e22]: ● LIVE
    - button "Settings" [ref=e23] [cursor=pointer]: •••
  - complementary [ref=e24]:
    - button "Collapse systems" [ref=e25] [cursor=pointer]: ‹
    - generic [ref=e26]:
      - generic [ref=e27]:
        - generic [ref=e28]: SYSTEMS
        - generic [ref=e29]: 7 COMPONENTS
      - button "COMPLETE SYSTEM SHOW ALL" [ref=e30] [cursor=pointer]:
        - text: COMPLETE SYSTEM
        - generic [ref=e31]: SHOW ALL
      - generic [ref=e32]:
        - generic [ref=e33]:
          - generic [ref=e34]:
            - button "− actuator" [expanded] [ref=e35] [cursor=pointer]
            - button "ISOLATE" [ref=e36] [cursor=pointer]
          - button "SG90 Servo component-servo-1" [ref=e37] [cursor=pointer]:
            - generic [ref=e39]: SG90 Servo
            - generic [ref=e40]: CONCEPTUAL
          - button "SG90 Servo component-servo-2" [ref=e41] [cursor=pointer]:
            - generic [ref=e43]: SG90 Servo
            - generic [ref=e44]: CONCEPTUAL
        - generic [ref=e45]:
          - generic [ref=e46]:
            - button "− electronics" [expanded] [ref=e47] [cursor=pointer]
            - button "ISOLATE" [ref=e48] [cursor=pointer]
          - button "ESP32 DevKit component-controller" [ref=e49] [cursor=pointer]:
            - generic [ref=e51]: ESP32 DevKit
            - generic [ref=e52]: CONCEPTUAL
        - generic [ref=e53]:
          - generic [ref=e54]:
            - button "− mechanical" [expanded] [ref=e55] [cursor=pointer]
            - button "ISOLATE" [ref=e56] [cursor=pointer]
          - button "Driven link component-mechanism-1" [ref=e57] [cursor=pointer]:
            - generic [ref=e59]: Driven link
            - generic [ref=e60]: CONCEPTUAL
          - button "Driven link component-mechanism-2" [ref=e61] [cursor=pointer]:
            - generic [ref=e63]: Driven link
            - generic [ref=e64]: CONCEPTUAL
        - generic [ref=e65]:
          - generic [ref=e66]:
            - button "− power" [expanded] [ref=e67] [cursor=pointer]
            - button "ISOLATE" [ref=e68] [cursor=pointer]
          - button "Low-voltage power source component-power" [ref=e69] [cursor=pointer]:
            - generic [ref=e71]: Low-voltage power source
            - generic [ref=e72]: CONCEPTUAL
        - generic [ref=e73]:
          - generic [ref=e74]:
            - button "− structure" [expanded] [ref=e75] [cursor=pointer]
            - button "ISOLATE" [ref=e76] [cursor=pointer]
          - button "Structural base component-support" [ref=e77] [cursor=pointer]:
            - generic [ref=e79]: Structural base
            - generic [ref=e80]: CONCEPTUAL
  - generic [ref=e84]:
    - button "FIT" [ref=e85] [cursor=pointer]
    - button "EXPLODE" [ref=e86] [cursor=pointer]
    - button "SOLID" [ref=e87] [cursor=pointer]
    - button "SHOW ALL" [ref=e88] [cursor=pointer]
  - complementary [ref=e89]:
    - button "Collapse inspector" [ref=e90] [cursor=pointer]: ›
    - generic [ref=e92]:
      - generic [ref=e93]:
        - generic [ref=e94]: WHAT-IF ANALYSIS
        - generic [ref=e95]: SG90 Servo
      - heading "SG90 Servo evaluated against Candidate Servo" [level=2] [ref=e96]
      - generic [ref=e97]: AI SEMANTIC REVIEW
      - generic [ref=e98]:
        - button "CURRENT" [ref=e99] [cursor=pointer]
        - button "CANDIDATE" [ref=e100] [cursor=pointer]
      - generic [ref=e101]:
        - generic [ref=e102]:
          - generic [ref=e103]: VERIFICATION
          - generic [ref=e104]: SUPPORTED
        - emphasis [ref=e105]: →
        - generic [ref=e106]:
          - generic [ref=e107]: CANDIDATE
          - generic [ref=e108]: SUPPORTED
      - generic [ref=e109]:
        - generic [ref=e110]:
          - generic [ref=e111]: CONFIDENCE
          - generic [ref=e112]: UNKNOWN
        - emphasis [ref=e113]: →
        - generic [ref=e114]:
          - generic [ref=e115]: CANDIDATE
          - generic [ref=e116]: HIGH
      - heading "SYSTEM IMPACT" [level=3] [ref=e117]
      - generic [ref=e118]:
        - article [ref=e119]:
          - generic [ref=e120]: AI COMPATIBILITY
          - generic [ref=e121]: The candidate preserves the target function and interfaces.
          - generic [ref=e122]: COMPATIBLE
        - article [ref=e123]:
          - generic [ref=e124]: ENGINEERING
          - generic [ref=e125]: Relationship connection-controller-servo-1-control-edge must be re-evaluated
        - article [ref=e126]:
          - generic [ref=e127]: ENGINEERING
          - generic [ref=e128]: Relationship connection-power-servo-1-ground-edge must be re-evaluated
        - article [ref=e129]:
          - generic [ref=e130]: ENGINEERING
          - generic [ref=e131]: Relationship connection-power-servo-1-power-edge must be re-evaluated
        - article [ref=e132]:
          - generic [ref=e133]: ENGINEERING
          - generic [ref=e134]: Relationship connection-servo-1-mechanism-1-mechanical-edge must be re-evaluated
        - article [ref=e135]:
          - generic [ref=e136]: ENGINEERING
          - generic [ref=e137]: Relationship connection-support-servo-1-mechanical-edge must be re-evaluated
      - heading "AFFECTED" [level=3] [ref=e138]
      - generic [ref=e139]:
        - button "ESP32 DevKit INSPECT" [ref=e140] [cursor=pointer]:
          - generic [ref=e141]: ESP32 DevKit
          - generic [ref=e142]: INSPECT
        - button "Driven link INSPECT" [ref=e143] [cursor=pointer]:
          - generic [ref=e144]: Driven link
          - generic [ref=e145]: INSPECT
        - button "Low-voltage power source INSPECT" [ref=e146] [cursor=pointer]:
          - generic [ref=e147]: Low-voltage power source
          - generic [ref=e148]: INSPECT
        - button "SG90 Servo INSPECT" [ref=e149] [cursor=pointer]:
          - generic [ref=e150]: SG90 Servo
          - generic [ref=e151]: INSPECT
        - button "SG90 Servo INSPECT" [ref=e152] [cursor=pointer]:
          - generic [ref=e153]: SG90 Servo
          - generic [ref=e154]: INSPECT
        - button "Structural base INSPECT" [ref=e155] [cursor=pointer]:
          - generic [ref=e156]: Structural base
          - generic [ref=e157]: INSPECT
      - heading "UNCERTAINTIES" [level=3] [ref=e158]
      - list [ref=e159]:
        - listitem [ref=e160]: Modified driver values require implementation confirmation.
      - generic [ref=e161]:
        - button "DISCARD" [ref=e162] [cursor=pointer]
        - button "APPLY CHANGE" [ref=e163] [cursor=pointer]
    - generic [ref=e164]:
      - generic [ref=e165]: TARGET
      - generic [ref=e166]: SG90 Servo
      - generic [ref=e167]: SERVO
      - button "CREATE WORK ITEM" [ref=e168] [cursor=pointer]
  - generic [ref=e169]: component-servo-1
  - generic [ref=e170]: Revision 1
  - slider "Explode amount" [ref=e171]: "0"
  - generic:
    - generic: AURA
    - generic: "Project ready with 7 components across 5 subsystems: 1 source-verified checks, 6 estimates, and 0 failed checks."
  - generic [ref=e172]:
    - generic [ref=e173]: AURA >
    - textbox "AURA command" [ref=e174]:
      - /placeholder: Ask, modify, inspect or compare SG90 Servo...
    - button "PREVIEW" [disabled] [ref=e175]
```

# Test source

```ts
  1  | import {expect,test,APIRequestContext} from "@playwright/test";
  2  | const backend="http://127.0.0.1:4184";
  3  | async function project(r:APIRequestContext){const x=await r.post(`${backend}/api/projects`,{data:{objective:`Design a low voltage two axis robotic arm with servo actuators and controller for round two lifecycle ${crypto.randomUUID()}`,planningMode:"deterministic_test"}});expect(x.ok()).toBeTruthy();return x.json()}
  4  | async function work(r:APIRequestContext,p:string,title:string){const x=await r.post(`${backend}/api/projects/${p}/work`,{data:{title}});expect(x.ok()).toBeTruthy();return x.json()}
  5  |
  6  | test("real workspace exposes Work creation and non-passive schematic zoom",async({page,request})=>{
  7  |  const errors:string[]=[];page.on("console",message=>{if(message.type()==="error")errors.push(message.text())});
  8  |  const p=await project(request);await page.goto(`${backend}/?projectId=${p.projectId}`);
  9  |  await expect(page.getByRole("button",{name:"WORK",exact:true})).toBeVisible();await page.getByRole("button",{name:"WORK",exact:true}).click();
  10 |  await expect(page.getByRole("button",{name:"ALL",exact:true})).toHaveClass(/active/);await expect(page.getByTestId("work-empty")).toContainText("No engineering work has been created for this project yet.");
  11 |  await page.getByRole("button",{name:"CREATE WORK ITEM"}).click();const create=page.getByRole("dialog");await create.getByLabel("Work item title").fill("Verify actuator capability");await create.getByLabel("Work item description").fill("Confirm actuator torque is sufficient.");await create.getByRole("button",{name:"CREATE",exact:true}).click();
  12 |  await expect(page.getByTestId("work-item-info")).toContainText("Verify actuator capability");await expect(page.getByTestId("work-item-info")).toContainText("Confirm actuator torque is sufficient.");await expect(page.getByTestId("work-view")).toContainText("1 PLANNED");
  13 |  await page.getByRole("button",{name:"SCHEMATIC",exact:true}).click();const camera=page.getByTestId("schematic-camera");await camera.hover();await page.mouse.wheel(0,-120);
  14 |  expect(errors.filter(value=>value.includes("passive event listener"))).toEqual([]);
  15 | });
  16 |
  17 | test("real Work lifecycle enforces reasons, persists history, and updates summary",async({page,request})=>{
  18 |  const p=await project(request);await work(request,p.projectId,"Verify pitch actuator capability");await page.goto(`${backend}/?projectId=${p.projectId}`);await page.getByRole("button",{name:"WORK",exact:true}).click();await page.getByRole("button",{name:/Verify pitch actuator capability/}).click();let d=page.getByTestId("work-item-info");await d.getByRole("button",{name:"IN PROGRESS"}).click();await d.getByRole("button",{name:"PAUSED"}).click();const dialog=page.getByRole("dialog");await expect(dialog.getByRole("button",{name:"PAUSED"})).toBeDisabled();await dialog.getByRole("textbox").fill("Waiting for verified panel mass.");await dialog.getByRole("button",{name:"PAUSED"}).click();await page.reload();await page.getByRole("button",{name:"WORK",exact:true}).click();await page.getByRole("button",{name:/Verify pitch actuator capability/}).click();d=page.getByTestId("work-item-info");await expect(d).toContainText("PLANNED → IN PROGRESS");await expect(d).toContainText("IN PROGRESS → PAUSED");await d.getByRole("button",{name:"IN PROGRESS"}).click();await d.getByRole("button",{name:"COMPLETED"}).click();await expect(d).toContainText("COMPLETED");
  19 |  await work(request,p.projectId,"Enclosure design");await work(request,p.projectId,"Motor availability test");expect((await (await request.get(`${backend}/api/projects/${p.projectId}/work`)).json()).summary.total).toBe(3);
  20 | });
  21 |
  22 | test("real What-If isolates, applies one represented revision, and rejects stale candidate",async({page,request})=>{
> 23 |  const p=await project(request),g=await (await request.get(`${backend}/api/projects/${p.projectId}/graph`)).json(),target=g.entities.find((x:any)=>x.kind==="component"&&x.metadata?.family==="servo"),before=await (await request.get(`${backend}/api/projects/${p.projectId}`)).json();await page.goto(`${backend}/?projectId=${p.projectId}`);await expect(page.getByText("Select a component to explore an engineering change.")).toBeVisible();await page.getByRole("button",{name:new RegExp(target.id)}).click();await page.getByRole("button",{name:"WHAT IF?"}).click();await expect(page.locator(".scenario-target")).toContainText(target.name);await expect(page.getByRole("button",{name:"ANALYZE WITH AI"})).toBeDisabled();await page.getByLabel("Candidate engineering change").fill("Replace with Candidate Servo");await expect(page.getByRole("button",{name:"ANALYZE WITH AI"})).toBeEnabled();await page.getByRole("button",{name:"ANALYZE WITH AI"}).click();const panel=page.getByTestId("scenario-info");await expect(panel).toContainText("Candidate Servo");expect((await (await request.get(`${backend}/api/projects/${p.projectId}`)).json()).revision).toBe(before.revision);await panel.getByRole("button",{name:"DISCARD"}).click();
     |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            ^ Error: locator.click: Test timeout of 45000ms exceeded.
  24 |  const first=await (await request.post(`${backend}/api/projects/${p.projectId}/scenarios`,{data:{targetSemanticId:target.id,changeType:"REPLACE_COMPONENT",value:{name:"A"}}})).json(),second=await (await request.post(`${backend}/api/projects/${p.projectId}/scenarios`,{data:{targetSemanticId:target.id,changeType:"REPLACE_COMPONENT",value:{name:"B"}}})).json();expect((await request.post(`${backend}/api/projects/${p.projectId}/scenarios/${first.scenarioId}/apply`)).status()).toBe(404);const applied=await request.post(`${backend}/api/projects/${p.projectId}/scenarios/${second.scenarioId}/apply`);expect(applied.ok()).toBeTruthy();const result=await applied.json();expect(result.representations.some((x:any)=>x.revision===before.revision+1)).toBeTruthy();const stale=await (await request.post(`${backend}/api/projects/${p.projectId}/scenarios`,{data:{targetSemanticId:target.id,changeType:"REPLACE_COMPONENT",value:{name:"Stale"}}})).json(),newer=await (await request.post(`${backend}/api/projects/${p.projectId}/scenarios`,{data:{targetSemanticId:target.id,changeType:"REPLACE_COMPONENT",value:{name:"Newer"}}})).json();expect((await request.post(`${backend}/api/projects/${p.projectId}/scenarios/${newer.scenarioId}/apply`)).ok()).toBeTruthy();expect((await request.post(`${backend}/api/projects/${p.projectId}/scenarios/${stale.scenarioId}/apply`)).status()).toBe(404);
  25 | });
  26 |
  27 | test("What-If uncertainty can become explicit planned engineering work",async({page,request})=>{
  28 |  const p=await project(request),g=await request.get(`${backend}/api/projects/${p.projectId}/graph`).then(r=>r.json()),target=g.entities.find((x:any)=>x.kind==="component"&&x.metadata?.family==="servo");await page.goto(`${backend}/?projectId=${p.projectId}`);await page.getByRole("button",{name:new RegExp(target.id)}).click();await page.getByRole("button",{name:"WHAT IF?"}).click();await page.getByLabel("Candidate engineering change").fill("Replace with Candidate Servo");await page.getByRole("button",{name:"ANALYZE WITH AI"}).click();await page.locator(".scenario-target").getByRole("button",{name:"CREATE WORK ITEM"}).click();await expect(page.getByTestId("engineering-space")).toHaveClass(/mode-work/);await expect(page.getByTestId("work-item-info")).toContainText("Verify Candidate Servo capability");const state=await request.get(`${backend}/api/projects/${p.projectId}/work`).then(r=>r.json());expect(state.summary.total).toBe(1);expect(state.items[0].state).toBe("PLANNED");
  29 | });
  30 |
  31 | test("AI rejects a light sensor to servo substitution and keeps Apply disabled",async({page,request})=>{
  32 |  const created=await request.post(`${backend}/api/projects`,{data:{objective:`Build a tabletop two-axis solar tracker that automatically points a small solar panel toward the brightest light source using an Arduino Nano. ${crypto.randomUUID()}`,planningMode:"deterministic_test"}});expect(created.ok()).toBeTruthy();const p=await created.json(),g=await request.get(`${backend}/api/projects/${p.projectId}/graph`).then(r=>r.json()),sensor=g.entities.find((x:any)=>x.kind==="component"&&x.metadata?.family==="light_sensor");await page.goto(`${backend}/?projectId=${p.projectId}`);await page.getByRole("button",{name:new RegExp(`${sensor.id}$`)}).click();await page.getByRole("button",{name:"WHAT IF?"}).click();await page.getByLabel("Candidate engineering change").fill("Replace with servo");await page.getByRole("button",{name:"ANALYZE WITH AI"}).click();const panel=page.getByTestId("scenario-info");await expect(panel).toContainText("AI SEMANTIC REVIEW");await expect(panel).toContainText("DIRECT REPLACEMENT REJECTED");await expect(panel).toContainText("cannot provide ambient-light feedback");await expect(panel).toContainText("INCOMPATIBLE");await expect(panel.getByTestId("apply-scenario")).toBeDisabled();expect((await request.get(`${backend}/api/projects/${p.projectId}`).then(r=>r.json())).revision).toBe(p.revision);await page.screenshot({path:"test-results/aura-ai-scenario/light-sensor-servo-rejected.png",fullPage:true});
  33 | });
  34 |
```
