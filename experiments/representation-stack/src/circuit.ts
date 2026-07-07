import type { CircuitJson } from "circuit-json"
import irrigationCircuit from "./fixtures/irrigation-circuit.json"

export const generateIrrigationCircuit = (): CircuitJson => structuredClone(irrigationCircuit) as CircuitJson
export const referenceFromSchematicId = (id: string) => id.replace("schematic_", "")
