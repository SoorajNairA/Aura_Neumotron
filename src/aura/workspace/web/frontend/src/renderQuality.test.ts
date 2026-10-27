import {describe,expect,it} from "vitest";
import {qualityFor,SlowFrames} from "./renderQuality";

describe("render quality",()=>{
 it("uses studio effects only where they run smoothly",()=>{
  expect(qualityFor({webgl2:true,reducedMotion:false,slow:false})).toBe("high");
  expect(qualityFor({webgl2:false,reducedMotion:false,slow:false})).toBe("basic");
  expect(qualityFor({webgl2:true,reducedMotion:true,slow:false})).toBe("basic");
  expect(qualityFor({webgl2:true,reducedMotion:false,slow:true})).toBe("basic");
 });
 it("calls frames slow only when most of the recent ones exceed 33 ms",()=>{
  const frames=new SlowFrames(10);
  for(let i=0;i<9;i++)frames.add(50);expect(frames.slow).toBe(false);
  frames.add(50);expect(frames.slow).toBe(true);
  const mixed=new SlowFrames(10);for(let i=0;i<10;i++)mixed.add(i%2?50:10);expect(mixed.slow).toBe(false);
 });
});
