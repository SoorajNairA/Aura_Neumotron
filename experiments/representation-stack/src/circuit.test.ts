import { describe,expect,it } from "vitest"
import { generateIrrigationCircuit,referenceFromSchematicId } from "./circuit"
import { semanticForReference } from "./domain"

describe("irrigation Circuit JSON",()=>{
  it("contains every required semantic component",()=>{const json=generateIrrigationCircuit() as Array<Record<string,unknown>>;for(const ref of ["U1","S1","Q1","D1","M1","BT1"]){expect(json.some(e=>e.type==="schematic_component"&&e.schematic_component_id===`schematic_${ref}`)).toBe(true);expect(semanticForReference(ref)).toMatch(/^component-/)}})
  it("maps viewer IDs without fuzzy matching",()=>expect(referenceFromSchematicId("schematic_Q1")).toBe("Q1"))
})
