import { useEffect, useMemo, useRef, useState } from "react"
import { SchematicViewer } from "@tscircuit/schematic-viewer"
import { CadGenerator } from "./cad"
import { generateIrrigationCircuit, referenceFromSchematicId } from "./circuit"
import { referenceForSemantic, semanticForReference, type RepresentationArtifact, type SemanticId } from "./domain"
import { RepresentationScene } from "./scene"

const CATALOGUE = { id: "bearing_608zz", semanticId: "component-catalogue-bearing" as SemanticId }

export default function App() {
  const host = useRef<HTMLDivElement>(null)
  const scene = useRef<RepresentationScene>()
  const [selected, setSelected] = useState<SemanticId>()
  const [artifact, setArtifact] = useState<RepresentationArtifact>()
  const [cadArtifacts, setCadArtifacts] = useState<RepresentationArtifact[]>([])
  const [cadStatus, setCadStatus] = useState("CAD generation pending")
  const [initMs, setInitMs] = useState(0)
  const circuit = useMemo(() => generateIrrigationCircuit(), [])
  const choose = (id: SemanticId) => { setSelected(id); scene.current?.select(id); setArtifact(scene.current?.artifact(id)) }

  useEffect(() => {
    if (!host.current) return
    const view = new RepresentationScene(host.current, (id) => { setSelected(id); setArtifact(view.artifact(id)) })
    scene.current = view
    view.addProxy("component-controller", "Controller proxy", [-30, -70, 8])
    view.addProxy("component-driver", "MOSFET driver proxy", [5, -70, 8], "driver")
    view.addProxy("component-pump", "Pump proxy", [42, -70, 12], "pump")
    view.addProxy("component-soil-sensor", "Soil sensor proxy", [75, -70, 8])
    view.addProxy(CATALOGUE.semanticId, "608ZZ catalogue proxy — model licence rejected", [108, -70, 12], "catalogue")
    const generator = new CadGenerator()
    void (async () => {
      try {
        setInitMs(await generator.init())
        const results = await generator.generate((id, status) => setCadStatus(`${id}: ${status}`))
        setCadArtifacts(results.map((result, index) => view.addCad(result, index)))
        setCadStatus("CAD generation succeeded")
      } catch (error) {
        console.error("CAD generation failed; semantic proxies remain", error)
        setCadStatus(`CAD generation failed — proxy representation used: ${String(error)}`)
      }
    })()
    return () => { generator.dispose(); view.dispose() }
  }, [])

  const schematicClick = (id: string) => { const semantic = semanticForReference(referenceFromSchematicId(id)); if (semantic) choose(semantic) }
  return <main>
    <header><div><p className="eyebrow">AURA EXPERIMENT 01</p><h1>Representation stack proof</h1></div><div className={`status ${cadStatus.includes("succeeded") ? "ok" : ""}`} data-testid="cad-status">{cadStatus}</div></header>
    <section className="workspace">
      <div className="viewport"><div ref={host} className="canvas" data-testid="three-canvas"/><div className="part-results">{cadArtifacts.map(item => <button key={item.semanticId} data-cad-part={item.semanticId} onClick={() => choose(item.semanticId)}><b>{item.semanticId}</b><span>{item.triangles} triangles · {item.generationMs.toFixed(0)} ms · {item.dimensionsMm.map(v => v.toFixed(1)).join("×")} mm</span></button>)}</div><div className="toolbar"><button onClick={() => scene.current?.resetCamera()}>Reset camera</button><button onClick={() => scene.current?.isolate(true)}>Isolate selected</button><button onClick={() => scene.current?.isolate(false)}>Show all</button><label>Assemble <input aria-label="Explode" type="range" min="0" max="1" step=".01" defaultValue="0" onChange={e => scene.current?.explode(Number(e.target.value))}/> Explode</label></div></div>
      <aside className="debug"><h2>Semantic debug</h2><dl><dt>Selected semantic ID</dt><dd data-testid="selected-id">{selected ?? "none"}</dd><dt>Circuit reference</dt><dd>{selected ? referenceForSemantic(selected) ?? "no mapping" : "none"}</dd><dt>Object source</dt><dd>{artifact?.source ?? "—"}</dd><dt>CAD generator</dt><dd>{artifact?.source === "cascade-core" ? "cascade-core 2.0.6" : "—"}</dd><dt>Triangles</dt><dd>{artifact?.triangles ?? "—"}</dd><dt>Bounding box (mm)</dt><dd>{artifact?.dimensionsMm.map(v => v.toFixed(1)).join(" × ") ?? "—"}</dd><dt>Generation</dt><dd>{artifact?.status ?? "—"}</dd></dl><div className="metric">OpenCascade init: {initMs ? `${initMs.toFixed(0)} ms` : "pending"}</div><div className="warning" data-testid="catalogue-status"><b>Catalogue model licence rejected</b><br/>step.parts ID {CATALOGUE.id}; API omits individual model licence, attribution, units and orientation. Network model not loaded. Proxy representation used.</div></aside>
    </section>
    <section className="schematic"><div><p className="eyebrow">GENERATED CIRCUIT JSON</p><h2>Irrigation pump driver</h2></div><div className="viewer" data-testid="schematic"><SchematicViewer circuitJson={circuit as never} editingEnabled={false} onSchematicComponentClicked={({ schematicComponentId }) => schematicClick(schematicComponentId)}/></div><div className="symbols">{["U1", "S1", "Q1", "D1", "M1", "BT1"].map(ref => <button key={ref} data-symbol={ref} className={referenceForSemantic(selected!) === ref ? "selected" : ""} onClick={() => { const id = semanticForReference(ref); if (id) choose(id) }}><b>{ref}</b><span>{semanticForReference(ref)}</span></button>)}</div></section>
    <footer>Units: millimetres · +X forward · +Y left · +Z up · CAD runs in cascade-core Web Worker</footer>
  </main>
}
