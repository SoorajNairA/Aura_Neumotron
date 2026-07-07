import { writeFile } from "node:fs/promises"
import { Battery, Board, Chip, Circuit, Diode, Mosfet, Resistor } from "@tscircuit/core"

const generationStarted = performance.now()
const positions = { U1: [0, 2], S1: [-4, 2], Q1: [2, 0], D1: [4, 0], M1: [6, 0], BT1: [0, -3] }
const semantics = { U1: "component-controller", Q1: "component-driver", D1: "component-flyback-diode", M1: "component-pump", S1: "component-soil-sensor", BT1: "component-power-source" }
const circuit = new Circuit()
const board = new Board({ width: "80mm", height: "50mm" })
circuit.add(board)
;[
  new Chip({ name: "U1", footprint: "soic8", pinLabels: { 1: "VCC", 2: "GND" } }),
  new Resistor({ name: "S1", resistance: "10k", footprint: "0402" }),
  new Mosfet({ name: "Q1", channelType: "n", mosfetMode: "enhancement", footprint: "sot23" }),
  new Diode({ name: "D1", footprint: "sod123" }),
  new Resistor({ name: "M1", resistance: "5", footprint: "1206" }),
  new Battery({ name: "BT1", capacity: "2000mAh" }),
].forEach(component => board.add(component))

const json = circuit.getCircuitJson()
const namesBySource = new Map(json.filter(e => e.type === "source_component").map(e => [e.source_component_id, e.name]))
const oldToNew = new Map()
for (const element of json.filter(e => e.type === "schematic_component")) {
  const reference = namesBySource.get(element.source_component_id)
  if (!reference || !positions[reference]) continue
  oldToNew.set(element.schematic_component_id, `schematic_${reference}`)
  element.schematic_component_id = `schematic_${reference}`
  element.center = { x: positions[reference][0], y: positions[reference][1] }
  element.rotation = 0
  element.aura_semantic_id = semantics[reference]
}
for (const port of json.filter(e => e.type === "schematic_port")) port.schematic_component_id = oldToNew.get(port.schematic_component_id) ?? port.schematic_component_id
[["BT1","U1"],["BT1","S1"],["S1","U1"],["U1","Q1"],["Q1","M1"],["M1","D1"],["D1","BT1"],["Q1","BT1"]].forEach(([from,to],index)=>json.push({type:"schematic_trace",schematic_trace_id:`aura_trace_${index}`,edges:[{from:{x:positions[from][0],y:positions[from][1]},to:{x:positions[to][0],y:positions[to][1]}}]}))
await writeFile(new URL("../src/fixtures/irrigation-circuit.json", import.meta.url), `${JSON.stringify(json, null, 2)}\n`)
console.log(`Generated ${json.length} Circuit JSON elements with @tscircuit/core in ${(performance.now() - generationStarted).toFixed(1)} ms`)
