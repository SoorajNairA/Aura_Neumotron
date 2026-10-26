import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {describe,expect,it} from "vitest";
import {fanControl} from "./fanControl";

// Same truth table the generated firmware's C++ rule is tested against.
const cases:[boolean,number|null,boolean][]=JSON.parse(readFileSync(resolve(__dirname,"../../../../../../tests/fixtures/fan_hysteresis_cases.json"),"utf8"));

describe("behavioral fan control",()=>{
 it("matches the firmware hysteresis truth table",()=>{for(const [prev,t,expected] of cases)expect(fanControl(prev,t,26,24).on,`${prev} ${t}`).toBe(expected)});
 it("explains which rule applied, including the inclusive boundaries",()=>{
  expect(fanControl(false,26,26,24).reason).toBe("above_on");
  expect(fanControl(true,24,26,24).reason).toBe("below_off");
  expect(fanControl(true,25,26,24).reason).toBe("in_band");
  expect(fanControl(false,null,26,24).reason).toBe("sensor_fault");
 });
 it("follows custom thresholds",()=>{expect(fanControl(false,29,30,28).on).toBe(false);expect(fanControl(false,30,30,28).on).toBe(true)});
});
