export type SemanticId = `component-${string}`
export type RepresentationStatus = "pending" | "succeeded" | "failed" | "proxy"
export type SourceKind = "cascade-core" | "step.parts" | "proxy"

export interface RepresentationInput {
  semanticId: SemanticId
  label: string
  source: SourceKind
}
export interface RepresentationArtifact extends RepresentationInput {
  status: RepresentationStatus
  triangles: number
  generationMs: number
  dimensionsMm: [number, number, number]
  error?: string
}
export interface SemanticMapping {
  reference: string
  semanticId: SemanticId
}

export const semanticMappings: SemanticMapping[] = [
  { reference: "U1", semanticId: "component-controller" },
  { reference: "Q1", semanticId: "component-driver" },
  { reference: "D1", semanticId: "component-flyback-diode" },
  { reference: "M1", semanticId: "component-pump" },
  { reference: "S1", semanticId: "component-soil-sensor" },
  { reference: "BT1", semanticId: "component-power-source" },
]
export const semanticForReference = (reference: string) => semanticMappings.find((item) => item.reference === reference)?.semanticId
export const referenceForSemantic = (semanticId: SemanticId) => semanticMappings.find((item) => item.semanticId === semanticId)?.reference

export const nextStatus = (current: RepresentationStatus, event: "start" | "success" | "failure" | "fallback"): RepresentationStatus => {
  const transitions: Record<RepresentationStatus, Partial<Record<typeof event, RepresentationStatus>>> = {
    pending: { success: "succeeded", failure: "failed", fallback: "proxy" },
    succeeded: { start: "pending" }, failed: { start: "pending", fallback: "proxy" }, proxy: { start: "pending" },
  }
  return transitions[current][event] ?? current
}

export interface CatalogueMetadata { id: string; modelLicense?: string; attribution?: string; originalUnits: "mm"; originalUp: "+Z" }
export const validateCatalogueLicense = (metadata: CatalogueMetadata) => Boolean(metadata.modelLicense && metadata.attribution)
export const normalizeCataloguePoint = ([x, y, z]: [number, number, number], units: "mm" | "m", sourceUp: "+Y" | "+Z"): [number, number, number] => {
  const scale = units === "m" ? 1000 : 1
  return sourceUp === "+Y" ? [x * scale, -z * scale, y * scale] : [x * scale, y * scale, z * scale]
}
