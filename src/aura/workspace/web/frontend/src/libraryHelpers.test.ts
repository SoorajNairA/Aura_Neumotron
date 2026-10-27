import {describe,expect,it} from "vitest";
import {CatalogueItem,factLabel,filterParts,priceLabel} from "./libraryHelpers";

const item=(id:string,family:string,partNumber:string,manufacturer="Generic",price:CatalogueItem["price"]=null):CatalogueItem=>
 ({componentDefinitionId:id,family,manufacturer,partNumber,properties:{},interfaces:[],evidenceIds:[],price});
const items=[item("ds18b20-module","temperature_sensor","DS18B20 module","Analog Devices"),item("dc-fan-5v","fan","5 V brushless fan"),item("esp32-devkit-v1","microcontroller_board","ESP32-DevKitC","Espressif")];

describe("filterParts",()=>{
 it("matches part number, manufacturer, family and id case-insensitively",()=>{
  expect(filterParts(items,"ds18",null).map(i=>i.componentDefinitionId)).toEqual(["ds18b20-module"]);
  expect(filterParts(items,"ESPRESSIF",null).map(i=>i.componentDefinitionId)).toEqual(["esp32-devkit-v1"]);
  expect(filterParts(items,"temperature",null)).toHaveLength(1);
 });
 it("filters by family and keeps everything for an empty query",()=>{
  expect(filterParts(items,"","fan").map(i=>i.componentDefinitionId)).toEqual(["dc-fan-5v"]);
  expect(filterParts(items,"  ",null)).toHaveLength(3);
 });
});

describe("priceLabel",()=>{
 it("says price unavailable without a dated price",()=>expect(priceLabel(items[0])).toBe("price unavailable"));
 it("shows the price with its retrieval date",()=>expect(priceLabel({...items[0],price:{usd:3.95,source:"https://example.com/x",retrieved:"2026-10-27"}})).toBe("$3.95 · example.com (retrieved 2026-10-27)"));
});

describe("labels keep qualifiers, assumptions and sources",()=>{
 it("shows the qualifier and tags curated assumptions",()=>{
  expect(factLabel({value:300,unit:"mA",evidenceId:"evidence-curated-component-assumptions",qualifier:"maximum"})).toBe("300 mA (maximum, assumption)");
  expect(factLabel({value:[3,5.5],unit:"V",evidenceId:"evidence-espressif-esp32",qualifier:"rated"})).toBe("3–5.5 V");
 });
 it("names the price source",()=>expect(priceLabel({price:{usd:3.95,source:"https://www.adafruit.com/product/374",retrieved:"2026-10-27"}})).toBe("$3.95 · adafruit.com (retrieved 2026-10-27)"));
});
