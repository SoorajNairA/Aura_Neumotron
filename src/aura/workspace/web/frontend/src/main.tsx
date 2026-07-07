import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { SchematicViewer } from "@tscircuit/schematic-viewer";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import "./styles.css";

type RecordData = {
  representationId: string;
  semanticIds: string[];
  type: string;
  status: string;
  artifactId?: string;
  generator?: string;
  generatorVersion?: string;
  error?: string;
};
type MeshInfo = {
  id: string;
  triangles: number;
  dimensions: string;
  status: string;
};
const projectId = new URLSearchParams(location.search).get("projectId");
const CAD_INITIALIZATION_TIMEOUT_MS = 10_000;
const withTimeout = <T,>(promise: Promise<T>, timeoutMs: number): Promise<T> =>
  Promise.race([
    promise,
    new Promise<never>((_, reject) =>
      setTimeout(
        () => reject(new Error(`CAD initialization timed out after ${timeoutMs} ms`)),
        timeoutMs,
      ),
    ),
  ]);
const postStatus = (
  record: RecordData,
  status: string,
  error?: string,
  metrics: Record<string, number> = {},
) =>
  fetch(
    `/api/projects/${projectId}/representations/${record.representationId}/status`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ status, error, metrics }),
    },
  );
const cadCode = (spec: any) => {
  const g = spec.geometry;
  if (g.operation === "loft")
    return `Loft([${g.sections.map((s: any) => `Translate([0,0,${s.z}],Circle(${s.radius},true))`).join(",")}]);`;
  if (g.operation === "pipe")
    return `Pipe(Circle(${g.radius}),BSpline(${JSON.stringify(g.path)}));`;
  if (g.operation === "filleted_enclosure")
    return `let b=Box(${g.width},${g.depth},${g.height},true);FilletEdges(b,${g.radius},Edges(b).ofType("Line").indices());`;
  throw new Error("Unsupported validated CAD operation");
};

class SceneView {
  scene = new THREE.Scene();
  camera: THREE.PerspectiveCamera;
  renderer: THREE.WebGLRenderer;
  controls: OrbitControls;
  nodes = new Map<string, THREE.Mesh>();
  ray = new THREE.Raycaster();
  pointer = new THREE.Vector2();
  constructor(host: HTMLElement, select: (id: string) => void) {
    this.scene.background = new THREE.Color(0x07111f);
    this.scene.up.set(0, 0, 1);
    this.camera = new THREE.PerspectiveCamera(
      45,
      host.clientWidth / Math.max(host.clientHeight, 1),
      0.1,
      2000,
    );
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(230, -260, 190);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(host.clientWidth, host.clientHeight);
    host.appendChild(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(0, 0, 35);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x172554, 3));
    const grid = new THREE.GridHelper(400, 40);
    grid.rotateX(Math.PI / 2);
    this.scene.add(grid);
    this.renderer.domElement.onclick = (e) => {
      const r = this.renderer.domElement.getBoundingClientRect();
      this.pointer.set(
        ((e.clientX - r.left) / r.width) * 2 - 1,
        (-(e.clientY - r.top) / r.height) * 2 + 1,
      );
      this.ray.setFromCamera(this.pointer, this.camera);
      const hit = this.ray.intersectObjects([...this.nodes.values()])[0]
        ?.object;
      if (hit) select(hit.userData.semanticId);
    };
    const loop = () => {
      requestAnimationFrame(loop);
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    };
    loop();
  }
  add(id: string, faces: any[], index: number) {
    const geometry = new THREE.BufferGeometry(),
      positions: number[] = [],
      normals: number[] = [],
      indices: number[] = [];
    let offset = 0;
    for (const f of faces) {
      positions.push(...f.vertex_coord);
      normals.push(...f.normal_coord);
      indices.push(...f.tri_indexes.map((i: number) => i + offset));
      offset += f.vertex_coord.length / 3;
    }
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(positions, 3),
    );
    geometry.setAttribute(
      "normal",
      new THREE.Float32BufferAttribute(normals, 3),
    );
    geometry.setIndex(indices);
    geometry.computeBoundingBox();
    const mesh = new THREE.Mesh(
      geometry,
      new THREE.MeshStandardMaterial({
        color: [0x2dd4bf, 0x60a5fa, 0xf59e0b][index],
      }),
    );
    mesh.position.x = (index - 1) * 120;
    mesh.userData.semanticId = id;
    this.nodes.set(id, mesh);
    this.scene.add(mesh);
    const size = new THREE.Vector3();
    geometry.boundingBox!.getSize(size);
    return {
      id,
      triangles: indices.length / 3,
      dimensions: [size.x, size.y, size.z].map((x) => x.toFixed(1)).join(" × "),
      status: "ready",
    };
  }
  proxy(id: string, index: number) {
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(25, 20, 12),
      new THREE.MeshStandardMaterial({ color: 0x7c3aed, wireframe: true }),
    );
    mesh.position.set((index - 1) * 55, -90, 8);
    mesh.userData.semanticId = id;
    this.nodes.set(id, mesh);
    this.scene.add(mesh);
  }
  select(id: string) {
    this.nodes.forEach((node, key) =>
      (node.material as THREE.MeshStandardMaterial).emissive.setHex(
        key === id ? 0x2563eb : 0,
      ),
    );
  }
}

function App() {
  const host = useRef<HTMLDivElement>(null),
    view = useRef<SceneView>();
  const [records, setRecords] = useState<RecordData[]>([]),
    [infos, setInfos] = useState<MeshInfo[]>([]),
    [selected, setSelected] = useState<string>(),
    [circuit, setCircuit] = useState<any[]>([]),
    [mapping, setMapping] = useState<Record<string, string>>({}),
    [message, setMessage] = useState("Semantic placeholders ready");
  const choose = (id: string) => {
    setSelected(id);
    view.current?.select(id);
    parent.postMessage(
      { type: "aura.representation.selection", semanticId: id },
      location.origin,
    );
  };
  useEffect(() => {
    if (!projectId || !host.current) return;
    view.current = new SceneView(host.current, choose);
    (async () => {
      const project = await (await fetch(`/api/projects/${projectId}`)).json();
      setRecords(project.representations);
      const mechanical = project.representations.filter(
        (r: RecordData) => r.type === "mechanical_3d",
      );
      mechanical.forEach((r: RecordData, i: number) =>
        view.current!.proxy(r.semanticIds[0], i),
      );
      const schematic = project.representations.find(
        (r: RecordData) => r.type === "circuit_schematic",
      );
      if (schematic?.artifactId) {
        const json = await (
          await fetch(`/api/artifacts/${schematic.artifactId}/content`)
        ).json();
        setCircuit(json);
        setMapping(
          Object.fromEntries(
            json
              .filter(
                (e: any) =>
                  e.type === "schematic_component" && e.aura_semantic_id,
              )
              .map((e: any) => [e.schematic_component_id, e.aura_semantic_id]),
          ),
        );
      }
      if (!mechanical.length) return;
      setMessage("Lazy-loading OpenCascade worker");
      const { CascadeEngine } = await import("cascade-core");
      const engine = new CascadeEngine({
        workerUrl: `${import.meta.env.BASE_URL}cascade-worker.js`,
      });
      try {
        const started = performance.now();
        for (const record of mechanical) await postStatus(record, "generating");
        await withTimeout(engine.init(), CAD_INITIALIZATION_TIMEOUT_MS);
        const next: MeshInfo[] = [];
        for (let i = 0; i < mechanical.length; i++) {
          const record = mechanical[i];
          try {
            const spec = await (
              await fetch(`/api/artifacts/${record.artifactId}/content`)
            ).json();
            const partStarted = performance.now();
            const result = await engine.evaluate(cadCode(spec), {
              maxDeviation: 0.35,
            });
            next.push(
              view.current!.add(
                record.semanticIds[0],
                result.meshData.faces,
                i,
              ),
            );
            await postStatus(record, "ready", undefined, {
              generationMs: performance.now() - partStarted,
              initializationMs: performance.now() - started,
            });
          } catch (error) {
            await postStatus(record, "failed", String(error));
            await postStatus(
              { ...record, status: "failed" },
              "fallback",
              String(error),
            );
            next.push({
              id: record.semanticIds[0],
              triangles: 0,
              dimensions: "proxy",
              status: "fallback",
            });
          }
        }
        setInfos(next);
        setMessage("Mechanical representations ready");
      } catch (error) {
        for (const record of mechanical) {
          await postStatus({ ...record, status: "generating" }, "failed", String(error));
          await postStatus({ ...record, status: "failed" }, "fallback", String(error));
        }
        setInfos(
          mechanical.map((record: RecordData) => ({
            id: record.semanticIds[0],
            triangles: 0,
            dimensions: "proxy",
            status: "fallback",
          })),
        );
        setMessage(`CAD failed — semantic proxies retained: ${String(error)}`);
      } finally {
        engine.dispose();
      }
    })();
  }, []);
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (
        event.origin === location.origin &&
        event.data?.type === "aura.workspace.selection"
      )
        choose(event.data.semanticId);
    };
    addEventListener("message", handler);
    return () => removeEventListener("message", handler);
  }, []);
  return (
    <main>
      <header>
        <b>Production representations</b>
        <span>{message}</span>
      </header>
      <section className="grid">
        <div className="three" ref={host} />
        <aside>
          <h3>Semantic selection</h3>
          <strong data-testid="selected">{selected ?? "none"}</strong>
          {infos.map((x) => (
            <button key={x.id} onClick={() => choose(x.id)}>
              {x.id}
              <small>
                {x.triangles} triangles · {x.dimensions} mm · {x.status}
              </small>
            </button>
          ))}
          <h3>Lifecycle</h3>
          {records.map((r) => (
            <small key={r.representationId}>
              {r.representationId}: {r.status}
            </small>
          ))}
        </aside>
      </section>
      <section className="circuit" data-testid="schematic">
        {circuit.length ? (
          <SchematicViewer
            circuitJson={circuit as never}
            editingEnabled={false}
            onSchematicComponentClicked={({ schematicComponentId }) => {
              const id = mapping[schematicComponentId];
              if (id) choose(id);
            }}
          />
        ) : (
          <div>Structured circuit fallback</div>
        )}
      </section>
      <nav>
        {Object.entries(mapping).map(([ref, id]) => (
          <button
            className={selected === id ? "selected" : ""}
            key={ref}
            onClick={() => choose(id)}
          >
            {ref.replace("schematic_", "")} → {id}
          </button>
        ))}
      </nav>
    </main>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
