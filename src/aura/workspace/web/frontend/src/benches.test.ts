import {describe,expect,it} from "vitest";
import {benchKind,ds18b20Reading} from "./benches";

describe("ds18b20Reading",()=>{
 it("rounds to the sensor's 0.0625 °C step",()=>{
  expect(ds18b20Reading(25.03,true)).toBe(25.0);
  expect(ds18b20Reading(25.04,true)).toBe(25.0625);
 });
 it("clamps to the -55..125 °C range",()=>{
  expect(ds18b20Reading(200,true)).toBe(125);
  expect(ds18b20Reading(-80,true)).toBe(-55);
 });
 it("reports -127 when disconnected",()=>expect(ds18b20Reading(20,false)).toBe(-127));
});

describe("benchKind",()=>{
 it("supports the DS18B20 and the fan only",()=>{
  expect(benchKind("temperature_sensor","ds18b20-module")).toBe("ds18b20");
  expect(benchKind("temperature_sensor","bme280-module")).toBeNull();
  expect(benchKind("fan","dc-fan-5v")).toBe("fan");
  expect(benchKind("resistor","resistor-4k7")).toBeNull();
  expect(benchKind(undefined,undefined)).toBeNull();
 });
});
