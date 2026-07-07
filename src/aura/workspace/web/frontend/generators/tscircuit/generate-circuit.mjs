import { performance } from "node:perf_hooks"
import { Battery, Board, Chip, Circuit, Diode, Mosfet, Resistor } from "@tscircuit/core"

const started = performance.now()
const readInput = async () => {
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  return JSON.parse(Buffer.concat(chunks).toString("utf8"))
}
const rejectExecutable = value => {
  if (Array.isArray(value)) return value.some(rejectExecutable)
  if (!value || typeof value !== "object") return false
  return Object.entries(value).some(([key, child]) => ["code","script","javascript","command","executable"].includes(key.toLowerCase()) || rejectExecutable(child))
}
const fail = message => { process.stderr.write(JSON.stringify({status:"failed",error:message})); process.exit(2) }

try {
  const request = await readInput()
  if (rejectExecutable(request)) fail("Executable fields are forbidden")
  if (!Array.isArray(request.components) || request.components.length < 1 || request.components.length > 100) fail("Component count must be 1-100")
  if (!Array.isArray(request.connections)) fail("Connections must be an array")
  const circuit = new Circuit(); const board = new Board({width:"80mm",height:"50mm"}); circuit.add(board)
  const sourceByReference = new Map()
  for (const component of request.components) {
    const common = {name:component.reference}
    let instance
    if (component.kind === "controller") instance = new Chip({...common,footprint:"soic8",pinLabels:{1:"VCC",2:"GND"}})
    else if (component.kind === "soil_sensor") instance = new Resistor({...common,resistance:"10k",footprint:"0402"})
    else if (component.kind === "mosfet") instance = new Mosfet({...common,channelType:"n",mosfetMode:"enhancement",footprint:"sot23"})
    else if (component.kind === "diode") instance = new Diode({...common,footprint:"sod123"})
    else if (component.kind === "motor") instance = new Resistor({...common,resistance:"5",footprint:"1206"})
    else if (component.kind === "power_source") instance = new Battery({...common,capacity:"2000mAh"})
    else fail(`Unsupported component kind: ${component.kind}`)
    board.add(instance); sourceByReference.set(component.reference, component)
  }
  const circuitJson = circuit.getCircuitJson()
  const namesBySource = new Map(circuitJson.filter(e=>e.type==="source_component").map(e=>[e.source_component_id,e.name]))
  const oldToNew = new Map(); const columns = Math.ceil(Math.sqrt(request.components.length))
  for (const element of circuitJson.filter(e=>e.type==="schematic_component")) {
    const reference=namesBySource.get(element.source_component_id); const index=request.components.findIndex(c=>c.reference===reference)
    if(index<0) continue
    oldToNew.set(element.schematic_component_id,`schematic_${reference}`); element.schematic_component_id=`schematic_${reference}`
    element.center={x:(index%columns)*3,y:-Math.floor(index/columns)*2}; element.rotation=0
    element.aura_semantic_id=sourceByReference.get(reference).semanticId
  }
  for(const port of circuitJson.filter(e=>e.type==="schematic_port")) port.schematic_component_id=oldToNew.get(port.schematic_component_id)??port.schematic_component_id
  request.connections.forEach((connection,index)=>circuitJson.push({type:"schematic_trace",schematic_trace_id:`aura_trace_${index}`,edges:[],aura_connection:connection}))
  const mapping=Object.fromEntries(request.components.map(component=>[component.reference,component.semanticId]))
  const generationMs=performance.now()-started
  process.stdout.write(JSON.stringify({status:"ready",circuitJson,semanticMapping:mapping,warnings:[],metrics:{generationMs}}))
} catch(error) { fail(error instanceof Error ? error.message : String(error)) }
