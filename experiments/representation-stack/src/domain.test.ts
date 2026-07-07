import { describe,expect,it } from "vitest"
import { nextStatus,normalizeCataloguePoint,referenceForSemantic,semanticForReference,validateCatalogueLicense } from "./domain"

describe("semantic mapping",()=>{
  it("maps explicitly in both directions",()=>{expect(semanticForReference("M1")).toBe("component-pump");expect(referenceForSemantic("component-driver")).toBe("Q1")})
})
describe("representation states",()=>{
  it("terminates failures through an explicit proxy",()=>{expect(nextStatus("pending","failure")).toBe("failed");expect(nextStatus("failed","fallback")).toBe("proxy")})
})
describe("coordinate normalization",()=>{
  it("converts metres and Y-up to AURA millimetres and Z-up",()=>expect(normalizeCataloguePoint([1,2,3],"m","+Y")).toEqual([1000,-3000,2000]))
})
describe("catalogue licensing",()=>{
  it("rejects metadata without both licence and attribution",()=>{expect(validateCatalogueLicense({id:"bearing_608zz",originalUnits:"mm",originalUp:"+Z"})).toBe(false);expect(validateCatalogueLicense({id:"x",modelLicense:"CC0-1.0",attribution:"Author",originalUnits:"mm",originalUp:"+Z"})).toBe(true)})
})
