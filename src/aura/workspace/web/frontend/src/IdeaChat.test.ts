import {describe,expect,it} from "vitest";
import {canPropose,costLine,slotBadge} from "./ideaHelpers";

const req=(fn:any,power:any)=>({function:fn,power,budget:{value:"",source:"assumption",status:"open"}});

describe("idea chat helpers",()=>{
 it("labels where a requirement came from",()=>{
  expect(slotBadge("user")).toBe("You said");expect(slotBadge("default")).toBe("Default");expect(slotBadge("assumption")).toBe("Assumed");
 });
 it("mirrors the backend readiness rule",()=>{
  const scope={status:"IN_SCOPE"};
  expect(canPropose({requirements:req({value:"x",status:"agreed"},{value:"USB",status:"proposed"}),scope})).toBe(true);
  expect(canPropose({requirements:req({value:"x",status:"proposed"},{value:"USB",status:"agreed"}),scope})).toBe(false);
  expect(canPropose({requirements:req({value:"x",status:"agreed"},{value:"",status:"open"}),scope})).toBe(false);
  expect(canPropose({requirements:req({value:"x",status:"agreed"},{value:"USB",status:"agreed"}),scope:{status:"OUT_OF_SCOPE"}})).toBe(false);
  expect(canPropose(undefined)).toBe(false);
 });
 it("states the cost as an estimate and counts unpriced parts",()=>{
  expect(costLine({totalUsd:15.02,estimate:true,excluded:["dc-fan-5v"]})).toBe("Estimate: $15.02 · 1 part unpriced");
  expect(costLine({totalUsd:0,estimate:true,excluded:[]})).toBe("Estimate: $0.00");
  expect(costLine({totalUsd:1,estimate:true,excluded:["a","b"]})).toBe("Estimate: $1.00 · 2 parts unpriced");
 });
});
