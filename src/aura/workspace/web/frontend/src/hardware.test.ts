import {describe,expect,it} from "vitest";
import {evidenceText,portLabel,uploadText} from "./hardware";

describe("hardware copy",()=>{
 it("never claims hardware without evidence",()=>{
  expect(evidenceText(null)).toBe("Not tried on hardware");
  expect(evidenceText(null,true)).toBe("Fake board (test) — not hardware evidence");
  expect(evidenceText({port:"COM5",revisionId:"revision-3",lines:12,firstSeen:"2026-10-28T14:02:11.5+00:00",agreement:"not checked"}))
   .toBe("Observed on hardware: COM5, revision revision-3, 12 lines, 2026-10-28 14:02 UTC");
 });
 it("labels ports without confirming the board",()=>{
  expect(portLabel({address:"COM5",label:"COM5",likelyEsp32:true,fake:false})).toBe("COM5 — likely ESP32 (unverified)");
  expect(portLabel({address:"COM1",label:"COM1",likelyEsp32:false,fake:false})).toBe("COM1");
  expect(portLabel({address:"FAKE0",label:"Fake board (test)",likelyEsp32:false,fake:true})).toBe("Fake board (test)");
 });
 it("says an upload is only a flash",()=>{
  expect(uploadText({status:"uploaded",port:"COM5",revisionId:"r2",uploadedAt:"2026-10-28T14:00:00+00:00",errors:[],fake:false,hint:null}))
   .toBe("Uploaded revision r2 to COM5 at 2026-10-28 14:00 UTC — not yet observed running");
  expect(uploadText({status:"failed",port:"COM5",revisionId:"r2",uploadedAt:"",errors:["Failed to connect"],fake:false,hint:"Hold BOOT on the board while uploading."}))
   .toBe("Upload failed: Failed to connect. Hold BOOT on the board while uploading.");
 });
});
