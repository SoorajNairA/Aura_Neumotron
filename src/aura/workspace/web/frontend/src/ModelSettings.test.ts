import {describe,expect,it} from "vitest";
import {slugify,testSummary} from "./ModelSettings";
import {modelBadge} from "./studio";

describe("model settings helpers",()=>{
 it("builds unique profile ids from names",()=>{
  expect(slugify("Work OpenAI!",[])).toBe("work-openai");
  expect(slugify("Work OpenAI",["work-openai"])).toBe("work-openai-2");
  expect(slugify("   ",[])).toBe("model");
 });
 it("summarises connection tests with the real error class",()=>{
  expect(testSummary({ok:true,latencyMs:120})).toBe("Connected · 120 ms");
  expect(testSummary({ok:false,code:"MODEL_AUTHENTICATION",message:"API key was rejected (401)"})).toBe("Authentication rejected: API key was rejected (401)");
  expect(testSummary({ok:false,code:"MODEL_TIMEOUT",message:"request exceeded 15s"})).toBe("Timed out: request exceeded 15s");
 });
 it("falls back to the active profile label only when the project has no model origin",()=>{
  expect(modelBadge({planningMode:"live_model"},"Work OpenAI")).toBe("Work OpenAI");
  expect(modelBadge({planningMode:"live_model",assessment:{planningOrigin:{provider:"nebius",model:"nvidia/nemotron-3-super-120b-a12b"}}},"Work OpenAI")).toBe("Nemotron · Nebius");
  expect(modelBadge({planningMode:"deterministic_fallback"},"Work OpenAI")).toBe("Offline fallback");
 });
});
