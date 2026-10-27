import {describe,expect,it} from "vitest";
import {applyPoll,evidenceText,portLabel,uploadText} from "./hardware";

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

describe("review fixes",()=>{
 it("treats evidence for another revision as not current",()=>{
  const evidence={port:"COM5",revisionId:"revision-1",lines:5,firstSeen:"2026-10-28T14:02:11+00:00",agreement:"not checked"};
  expect(evidenceText(evidence,false,"revision-2")).toBe("Not tried on hardware (last observed: revision revision-1)");
  expect(evidenceText(evidence,false,"revision-1")).toMatch(/^Observed on hardware: COM5/);
 });
 it("drops a poll answer that belongs to a project the user already left",()=>{
  const state={running:true,port:"COM5",fake:false,lines:[{seq:1,time:"",text:"b",telemetry:null}],wrongRevision:null,evidence:null};
  const body={running:true,port:"COM9",fake:false,lines:[{seq:7,time:"",text:"a",telemetry:null}],wrongRevision:null,evidence:null};
  expect(applyPoll(state,body,"project-a","project-b")).toBe(state);
  expect(applyPoll(state,body,"project-b","project-b").lines.map(line=>line.text)).toEqual(["b","a"]);
 });
});
