import {expect,test} from "@playwright/test";

test("narration feed restores semantic focus and user selection cancels it",async({page})=>{
 await page.goto("http://127.0.0.1:4184/");
 await page.getByLabel("Voice").uncheck();
 await page.locator("#objective").fill("Build a small ESP32 desk fan that automatically turns on when the room gets too warm for narration testing.");
 await page.locator("#mode").selectOption("deterministic_test");
 await page.locator("#create").click();
 await expect(page.locator(".narration-item").first()).toBeVisible();
 const grounded=page.locator(".narration-item").filter({hasText:/documentation supports|deterministic rule agree/i}).first();
 await grounded.click();
 await expect(page.locator(".component.aura-focus").first()).toBeVisible();
 await page.locator(".component").first().dispatchEvent("click");
 await expect(page.locator(".component.aura-focus")).toHaveCount(0);
 await expect(page.locator(".component.selected")).toHaveCount(1);
});

test("browser speech honors mute and historical reconnect never repeats narration",async({page})=>{
 await page.addInitScript(()=>{
  class Utterance {text:string;onend?:()=>void;onerror?:()=>void;constructor(text:string){this.text=text}}
  Object.defineProperty(window,"SpeechSynthesisUtterance",{value:Utterance});
  Object.defineProperty(window,"speechSynthesis",{value:{speak:(u:Utterance)=>{const n=+(localStorage.getItem("test.speech.count")||0);localStorage.setItem("test.speech.count",String(n+1));setTimeout(()=>u.onend?.(),0)},cancel:()=>{const n=+(localStorage.getItem("test.speech.cancel")||0);localStorage.setItem("test.speech.cancel",String(n+1))}}});
 });
 await page.goto("http://127.0.0.1:4184/");
 await page.getByLabel("Voice").check();
 await page.locator("#objective").fill("Build a small weather station that measures temperature humidity and pressure for speech testing.");
 await page.locator("#mode").selectOption("deterministic_test");
 await page.locator("#create").click();
 await expect.poll(()=>page.evaluate(()=>+(localStorage.getItem("test.speech.count")||0))).toBeGreaterThan(0);
 const spoken=await page.evaluate(()=>+(localStorage.getItem("test.speech.count")||0));
 await page.reload();
 await page.waitForTimeout(600);
 expect(await page.evaluate(()=>+(localStorage.getItem("test.speech.count")||0))).toBe(spoken);
 await page.getByLabel("Voice").uncheck();
 await page.locator("#stop-speaking").click();
 expect(await page.evaluate(()=>localStorage.getItem("aura.voice.enabled"))).toBe("false");
});
