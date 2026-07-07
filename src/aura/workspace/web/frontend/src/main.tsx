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
};
type Part = {
	semanticId: string;
	label: string;
	subsystem: string;
	parentAssembly: string;
	representationSource: string;
	dimensions: number[];
	assembledTransform: { position: number[] };
	explodedTransform: { position: number[] };
	verificationState: string;
};
type Assembly = {
	parts: Part[];
	relationships: { from: string; to: string; type: string }[];
	connectors: any[];
};
type Proposal = { proposalId:string; summary:string; operations:any[]; affectedSemanticIds:string[]; unaffectedAreas:string[]; artifactsToRegenerate:string[]; verification:{checks:any[]}; };
const projectId = new URLSearchParams(location.search).get("projectId"),
	CAD_TIMEOUT = 10000;
const timeout = <T,>(p: Promise<T>) =>
	Promise.race([
		p,
		new Promise<never>((_, r) =>
			setTimeout(
				() => r(new Error("CAD initialization timed out")),
				CAD_TIMEOUT,
			),
		),
	]);
const postStatus = (
	r: RecordData,
	status: string,
	error?: string,
	metrics = {},
) =>
	fetch(
		`/api/projects/${projectId}/representations/${r.representationId}/status`,
		{
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ status, error, metrics }),
		},
	);
const cadCode = (s: any) => {
	const g = s.geometry;
	if (g.operation === "loft")
		return `Loft([${g.sections.map((x: any) => `Translate([0,0,${x.z}],Circle(${x.radius},true))`).join(",")}]);`;
	if (g.operation === "pipe")
		return `Pipe(Circle(${g.radius}),BSpline(${JSON.stringify(g.path)}));`;
	if (g.operation === "filleted_enclosure")
		return `let b=Box(${g.width},${g.depth},${g.height},true);FilletEdges(b,${g.radius},Edges(b).ofType("Line").indices());`;
	throw Error("Unsupported CAD operation");
};

class SceneView {
	scene = new THREE.Scene();
	camera: THREE.PerspectiveCamera;
	renderer: THREE.WebGLRenderer;
	controls: OrbitControls;
	nodes = new Map<string, THREE.Group>();
	parts = new Map<string, Part>();
	ray = new THREE.Raycaster();
	pointer = new THREE.Vector2();
	selected?: string;
	hovered?: string;
	focused = new Set<string>();
	explode = 0;
	subsystem = "all";
	xray = false;
	connections = new THREE.Group();
	preview?: THREE.Object3D;
	constructor(
		host: HTMLElement,
		select: (id: string) => void,
		hover: (id?: string) => void,
	) {
		this.scene.background = new THREE.Color(0x07131e);
		this.scene.up.set(0, 0, 1);
		this.camera = new THREE.PerspectiveCamera(
			38,
			host.clientWidth / Math.max(host.clientHeight, 1),
			0.1,
			2500,
		);
		this.camera.up.set(0, 0, 1);
		this.camera.position.set(360, -430, 270);
		this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
		this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
		this.renderer.setSize(host.clientWidth, host.clientHeight);
		this.renderer.shadowMap.enabled = true;
		this.renderer.outputColorSpace = THREE.SRGBColorSpace;
		host.appendChild(this.renderer.domElement);
		this.controls = new OrbitControls(this.camera, this.renderer.domElement);
		this.controls.enableDamping = true;
		this.controls.target.set(15, 20, 45);
		this.scene.add(new THREE.HemisphereLight(0xddeeff, 0x152538, 2.2));
		const sun = new THREE.DirectionalLight(0xffffff, 3.2);
		sun.position.set(-180, -220, 330);
		sun.castShadow = true;
		this.scene.add(sun);
		const floor = new THREE.Mesh(
			new THREE.PlaneGeometry(650, 500),
			new THREE.MeshStandardMaterial({ color: 0x0b2430, roughness: 0.9 }),
		);
		floor.receiveShadow = true;
		floor.position.z = -2;
		this.scene.add(floor, this.connections);
		const pick = (e: PointerEvent) => {
			const r = this.renderer.domElement.getBoundingClientRect();
			this.pointer.set(
				((e.clientX - r.left) / r.width) * 2 - 1,
				(-(e.clientY - r.top) / r.height) * 2 + 1,
			);
			this.ray.setFromCamera(this.pointer, this.camera);
			return this.ray
				.intersectObjects([...this.nodes.values()], true)
				.find((x) => x.object.userData.semanticId)?.object.userData.semanticId;
		};
		this.renderer.domElement.onpointermove = (e) => {
			const id = pick(e);
			if (id !== this.hovered) {
				this.hovered = id;
				hover(id);
				this.style();
			}
		};
		this.renderer.domElement.onclick = (e) => {
			const id = pick(e);
			if (id) select(id);
		};
		this.renderer.domElement.ondblclick = (e) => {
			const id = pick(e);
			if (id) {
				select(id);
				this.inspect(id);
			}
		};
		const loop = () => {
			requestAnimationFrame(loop);
			this.controls.update();
			this.renderer.render(this.scene, this.camera);
		};
		loop();
	}
	material(id: string, proxy = true) {
		const colors: any = {
			"component-enclosure": 0x5b7890,
			"component-reservoir": 0x2e9f9b,
			"component-tubing": 0x49b8e8,
			"component-esp32": 0x16875b,
			"component-driver": 0x7057d8,
			"component-power": 0xd89a37,
			"component-pump": 0x376f9f,
			"component-sensor": 0xb6a23c,
		};
		return new THREE.MeshStandardMaterial({
			color: colors[id] || 0x64748b,
			metalness: id.includes("pump") ? 0.55 : 0.15,
			roughness: 0.38,
			transparent: id === "component-enclosure" && this.xray,
			opacity: id === "component-enclosure" && this.xray ? 0.22 : 1,
			wireframe: false,
		});
	}
	geometry(p: Part) {
		const [x, y, z] = p.dimensions;
		switch (p.semanticId) {
			case "component-reservoir":
				return new THREE.CylinderGeometry(x / 2, x / 2, y, 32);
			case "component-pump":
				return new THREE.CylinderGeometry(y / 2, y / 2, x, 24);
			case "component-tubing":
				return new THREE.TorusGeometry(42, 3, 10, 40, Math.PI * 1.35);
			case "component-sensor":
				return new THREE.BoxGeometry(x, y, z);
			default:
				return new THREE.BoxGeometry(x, y, z);
		}
	}
	load(a: Assembly) {
		for (const node of this.nodes.values()) this.scene.remove(node);
		this.nodes.clear();this.parts.clear();this.clearPreview();
		for (const p of a.parts) {
			this.parts.set(p.semanticId, p);
			const g = new THREE.Group();
			g.name = p.semanticId;
			const mesh = new THREE.Mesh(
				this.geometry(p),
				this.material(p.semanticId),
			);
			mesh.userData.semanticId = p.semanticId;
			mesh.castShadow = true;
			mesh.receiveShadow = true;
			if (p.semanticId === "component-reservoir") mesh.rotation.x = Math.PI / 2;
			if (p.semanticId === "component-pump") mesh.rotation.z = Math.PI / 2;
			if (p.semanticId === "component-tubing") {
				mesh.rotation.x = Math.PI / 2;
				mesh.position.set(5, 0, 15);
			}
			g.add(mesh);
			const detail = (geometry: THREE.BufferGeometry, color: number, position: number[]) => {
				const item = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color,metalness:.25,roughness:.35}));
				item.position.fromArray(position);item.userData.semanticId=p.semanticId;item.castShadow=true;g.add(item);
			};
			if (p.semanticId === "component-esp32") {
				detail(new THREE.BoxGeometry(15,13,4),0x17212b,[0,0,6]);
				detail(new THREE.BoxGeometry(5,22,3),0xc7cdd1,[-20,0,5]);
			}
			if (p.semanticId === "component-driver") {
				detail(new THREE.BoxGeometry(10,8,7),0x151b22,[2,0,7]);
				detail(new THREE.BoxGeometry(6,18,5),0x2d343c,[-9,0,6]);
			}
			if (p.semanticId === "component-power") {
				detail(new THREE.CylinderGeometry(5,5,22,18),0xd7dde0,[-13,0,0]);
				detail(new THREE.CylinderGeometry(5,5,22,18),0xd7dde0,[13,0,0]);
			}
			if (p.semanticId === "component-sensor") {
				detail(new THREE.BoxGeometry(4,2,62),0xc4a83e,[-6,0,-12]);
				detail(new THREE.BoxGeometry(4,2,62),0xc4a83e,[6,0,-12]);
			}
			g.position.fromArray(p.assembledTransform.position);
			this.nodes.set(p.semanticId, g);
			this.scene.add(g);
		}
		this.style();
	}
	showPreview(proposal: Proposal) {
		this.clearPreview();
		if (!proposal.affectedSemanticIds.includes("component-reservoir")) return;
		const part=this.parts.get("component-reservoir");if(!part)return;
		const width=proposal.operations.find(x=>x.path==="dimensions.width.value")?.newValue||part.dimensions[0];
		const length=proposal.operations.find(x=>x.path==="dimensions.length.value")?.newValue||part.dimensions[1];
		const mesh=new THREE.Mesh(new THREE.CylinderGeometry(width/2,width/2,length,32),new THREE.MeshBasicMaterial({color:0x63f5df,transparent:true,opacity:.28,wireframe:true,depthWrite:false}));
		mesh.rotation.x=Math.PI/2;mesh.position.fromArray(part.assembledTransform.position);mesh.userData.semanticId=part.semanticId;
		this.preview=mesh;this.scene.add(mesh);
	}
	clearPreview(){if(this.preview){this.scene.remove(this.preview);this.preview=undefined;}}
	addCad(id: string, faces: any[]) {
		const group = this.nodes.get(id);
		if (!group) return null;
		group.clear();
		const geo = new THREE.BufferGeometry(),
			pos: number[] = [],
			norm: number[] = [],
			idx: number[] = [];
		let offset = 0;
		for (const f of faces) {
			pos.push(...f.vertex_coord);
			norm.push(...f.normal_coord);
			idx.push(...f.tri_indexes.map((i: number) => i + offset));
			offset += f.vertex_coord.length / 3;
		}
		geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
		geo.setAttribute("normal", new THREE.Float32BufferAttribute(norm, 3));
		geo.setIndex(idx);
		geo.computeBoundingBox();
		const mesh = new THREE.Mesh(geo, this.material(id, false));
		mesh.userData.semanticId = id;
		mesh.castShadow = true;
		group.add(mesh);
		this.style();
		return idx.length / 3;
	}
	setExplode(amount: number, subsystem: string) {
		this.explode = amount;
		this.subsystem = subsystem;
		for (const [id, g] of this.nodes) {
			const p = this.parts.get(id)!;
			const active = subsystem === "all" || p.subsystem === subsystem;
			const t = active ? amount : 0;
			g.position.set(
				...(p.assembledTransform.position.map(
					(x, i) => x + (p.explodedTransform.position[i] - x) * t,
				) as [number, number, number]),
			);
		}
	}
	isolate(subsystem: string) {
		this.subsystem = subsystem;
		for (const [id, g] of this.nodes) {
			const p = this.parts.get(id)!;
			g.visible = subsystem === "all" || p.subsystem === subsystem;
		}
		this.style();
		if (subsystem === "electronics") this.preset("Electronics");
		else if (subsystem === "water") this.preset("Water");
		else if (subsystem === "sensor") this.preset("Side");
		else this.preset("Assembly");
	}
	setXray(on: boolean) {
		this.xray = on;
		const mesh = this.nodes.get("component-enclosure")
			?.children[0] as THREE.Mesh;
		if (mesh) mesh.material = this.material("component-enclosure");
	}
	style() {
		for (const [id, g] of this.nodes)
			g.traverse((o) => {
				if (!(o instanceof THREE.Mesh)) return;
				const m = o.material as THREE.MeshStandardMaterial;
				m.emissive.setHex(id === this.selected ? 0x124b7a : this.focused.has(id) ? 0x6b4d12 : id === this.hovered ? 0x22533d : 0);
				m.opacity =
					this.subsystem !== "all" &&
					this.parts.get(id)?.subsystem !== this.subsystem
						? 0.12
						: id === "component-enclosure" && this.xray
							? 0.22
							: 1;
				m.transparent = m.opacity < 1;
			});
	}
	select(id: string) {
		this.selected = id;
		this.style();
		this.drawConnections(id);
	}
	focus(ids: string[]) { this.focused = new Set(ids); this.style(); }
	drawConnections(id: string) {
		this.connections.clear();
		const links: any = {
			"component-esp32": ["component-driver"],
			"component-driver": ["component-esp32", "component-pump"],
			"component-pump": [
				"component-driver",
				"component-reservoir",
				"component-tubing",
			],
			"component-reservoir": ["component-pump"],
			"component-tubing": ["component-pump"],
		};
		for (const other of links[id] || []) {
			const a = this.nodes.get(id)?.position,
				b = this.nodes.get(other)?.position;
			if (!a || !b) continue;
			const geo = new THREE.BufferGeometry().setFromPoints([a, b]);
			const line = new THREE.Line(
				geo,
				new THREE.LineDashedMaterial({
					color: 0xffd166,
					dashSize: 8,
					gapSize: 4,
				}),
			);
			line.computeLineDistances();
			this.connections.add(line);
		}
	}
	inspect(id: string) {
		const g = this.nodes.get(id);
		if (!g) return;
		this.controls.target.copy(g.position);
		const offset = new THREE.Vector3(100, -130, 85);
		this.camera.position.copy(g.position).add(offset);
		for (const [key, node] of this.nodes)
			node.visible = key === id || key === "component-enclosure";
	}
	showAll() {
		for (const g of this.nodes.values()) g.visible = true;
		this.subsystem = "all";
		this.style();
	}
	preset(name: string) {
		const p: any = {
			Assembly: [360, -430, 270],
			Electronics: [260, -150, 150],
			Water: [-280, -260, 180],
			Top: [20, 20, 560],
			Side: [450, 20, 120],
		};
		this.camera.position.fromArray(p[name]);
		this.controls.target.set(name === "Water" ? -70 : 60, 20, 45);
	}
}

function App() {
	const host = useRef<HTMLDivElement>(null),
		view = useRef<SceneView>();
	const [assembly, setAssembly] = useState<Assembly>();
	const [records, setRecords] = useState<RecordData[]>([]),
		[selected, setSelected] = useState<string>(),
		[hovered, setHovered] = useState<string>(),
		[circuit, setCircuit] = useState<any[]>([]),
		[mapping, setMapping] = useState<Record<string, string>>({}),
		[message, setMessage] = useState("Loading assembly"),
		[explode, setExplode] = useState(0),
		[subsystem, setSubsystem] = useState("all"),
		[xray, setXray] = useState(false),
		[request,setRequest]=useState(""),
		[proposal,setProposal]=useState<Proposal>(),
		[busy,setBusy]=useState(false),
		[revision,setRevision]=useState(0),
		[metrics, setMetrics] = useState<Record<string, number>>({});
	const refresh=async()=>{const [project,a]=await Promise.all([fetch(`/api/projects/${projectId}`).then(r=>r.json()),fetch(`/api/projects/${projectId}/assembly`).then(r=>r.json())]);setRevision(project.revision);setRecords(project.representations);setAssembly(a);view.current?.load(a);return project;};
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
		view.current = new SceneView(host.current, choose, setHovered);
		(async () => {
			const started = performance.now(),
				project = await (await fetch(`/api/projects/${projectId}`)).json(),
				a = await (await fetch(`/api/projects/${projectId}/assembly`)).json();
			setAssembly(a);
			setRevision(project.revision);
			setRecords(project.representations);
			view.current!.load(a);
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
			const mechanical = project.representations.filter(
				(r: RecordData) => r.type === "mechanical_3d",
			);
			if (!mechanical.length) {
				setMessage("Assembly ready");
				return;
			}
			setMessage("Generating parametric assembly parts");
			const { CascadeEngine } = await import("cascade-core"),
				engine = new CascadeEngine({
					workerUrl: `${import.meta.env.BASE_URL}cascade-worker.js`,
				});
			try {
				for (const r of mechanical) await postStatus(r, "generating");
				const init = performance.now();
				await timeout(engine.init());
				let triangles = 0,
					first = 0;
				for (const r of mechanical) {
					const ps = performance.now();
					try {
						const spec = await (
								await fetch(`/api/artifacts/${r.artifactId}/content`)
							).json(),
							result = await engine.evaluate(cadCode(spec), {
								maxDeviation: 0.35,
							});
						triangles +=
							view.current!.addCad(r.semanticIds[0], result.meshData.faces) ||
							0;
						if (!first) first = performance.now() - ps;
						await postStatus(r, "ready", undefined, {
							generationMs: performance.now() - ps,
						});
					} catch (e) {
						await postStatus(r, "failed", String(e));
						await postStatus(
							{ ...r, status: "failed" } as any,
							"fallback",
							String(e),
						);
					}
				}
				setMetrics({
					triangles,
					firstMechanicalMs: first,
					assemblyMs: performance.now() - started,
					cadInitializationMs: performance.now() - init,
				});
				setMessage("Coherent irrigation assembly ready");
			} catch (e) {
				setMessage(`CAD failed — intentional proxies retained: ${e}`);
			} finally {
				engine.dispose();
			}
		})();
	}, []);
	useEffect(() => {
		const h = (e: MessageEvent) => {
			if (
				e.origin === location.origin &&
				e.data?.type === "aura.workspace.selection"
			)
				choose(e.data.semanticId);
			if (
				e.origin === location.origin &&
				e.data?.type === "aura.workspace.focus"
			)
				view.current?.focus(e.data.semanticIds || []);
		};
		addEventListener("message", h);
		return () => removeEventListener("message", h);
	}, []);
	const part = assembly?.parts.find((p) => p.semanticId === selected);
	const changeExplode = (v: number) => {
		setExplode(v);
		view.current?.setExplode(v / 100, subsystem);
	};
	const isolate = (s: string) => {
		setSubsystem(s);
		view.current?.isolate(s);
		view.current?.setExplode(explode / 100, s);
	};
	const previewChange=async()=>{if(!selected||!request.trim())return;setBusy(true);try{const response=await fetch(`/api/projects/${projectId}/modification-proposals`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({projectId,baseRevision:revision,selectedSemanticIds:[selected],request,mode:"automatic"})});const body=await response.json();if(!response.ok)throw Error(body.detail?.code||"Proposal failed");setProposal(body);view.current?.showPreview(body);setMessage("Verified change ready to preview");}catch(e){setMessage(String(e));}finally{setBusy(false);}};
	const cancelChange=async()=>{if(proposal)await fetch(`/api/projects/${projectId}/modification-proposals/${proposal.proposalId}`,{method:"DELETE"});setProposal(undefined);view.current?.clearPreview();setMessage("Preview cancelled");};
	const applyChange=async()=>{if(!proposal)return;setBusy(true);try{const response=await fetch(`/api/projects/${projectId}/modification-proposals/${proposal.proposalId}/commit`,{method:"POST"});if(!response.ok)throw Error("Commit failed");await refresh();setProposal(undefined);setMessage("Verified change applied");}catch(e){setMessage(String(e));}finally{setBusy(false);}};
	const undo=async()=>{setBusy(true);try{const response=await fetch(`/api/projects/${projectId}/revisions/undo`,{method:"POST"});if(!response.ok)throw Error("Nothing to undo");await refresh();setMessage("Previous revision restored as a new revision");}catch(e){setMessage(String(e));}finally{setBusy(false);}};
	return (
		<main>
			<header>
				<div>
					<b>AURA Physical Assembly</b>
					<span>{message}</span>
				</div>
				<div className="toolbar">
					<button onClick={() => changeExplode(explode ? 0 : 100)}>
						{explode ? "Assemble" : "Explode"}
					</button>
					<input
						data-testid="explode-slider"
						aria-label="Explode amount"
						type="range"
						min="0"
						max="100"
						value={explode}
						onChange={(e) => changeExplode(+e.target.value)}
					/>
					<span>{explode}%</span>
					<button
						onClick={() => {
							setXray(!xray);
							view.current?.setXray(!xray);
						}}
					>
						X-ray shell
					</button>
					<button onClick={() => view.current?.showAll()}>Show all</button>
				</div>
			</header>
			<div className="camera">
				{["Assembly", "Electronics", "Water", "Top", "Side"].map((x) => (
					<button key={x} onClick={() => view.current?.preset(x)}>
						{x}
					</button>
				))}
				<span>Isolate:</span>
				{["all", "electronics", "water", "sensor"].map((x) => (
					<button
						className={subsystem === x ? "active" : ""}
						key={x}
						onClick={() => isolate(x)}
					>
						{x}
					</button>
				))}
			</div>
			<section className="grid">
				<div className="three" ref={host} />
				<aside>
					<h3>Verified modification <small>Revision {revision}</small></h3>
					<textarea data-testid="modification-request" aria-label="Requested change" value={request} onChange={e=>setRequest(e.target.value)} placeholder="Describe a change to the selected component" />
					<div className="change-actions"><button data-testid="preview-change" disabled={busy||!selected||!request.trim()} onClick={previewChange}>Preview verified change</button><button data-testid="undo-change" disabled={busy||revision<2} onClick={undo}>Undo</button></div>
					{proposal&&<div className="proposal" data-testid="proposal-preview"><h4>{proposal.summary}</h4><b>Requested change</b><p>{request}</p><b>Operations</b><ul>{proposal.operations.map((x,i)=><li key={i}>{x.path}: {String(x.oldValue)} → {String(x.newValue)}</li>)}</ul><b>Affected components</b><p>{proposal.affectedSemanticIds.join(", ")}</p><b>Regenerated artifacts</b><p>{proposal.artifactsToRegenerate.join(", ")}</p><b>Verification</b><ul>{proposal.verification.checks.map((x,i)=><li key={i} className={x.state.toLowerCase()}>{x.state}: {x.message}</li>)}</ul><b>Unchanged areas</b><p>{proposal.unaffectedAreas.join(", ")}</p><div className="change-actions"><button data-testid="apply-change" disabled={busy} onClick={applyChange}>Apply Change</button><button data-testid="cancel-change" disabled={busy} onClick={cancelChange}>Cancel</button></div></div>}
					<h3>Part inspection</h3>
					<strong data-testid="selected">
						{selected || "Select a physical part"}
					</strong>
					{hovered && (
						<p className="hover-label">
							Hover:{" "}
							{assembly?.parts.find((p) => p.semanticId === hovered)?.label}
						</p>
					)}
					{part ? (
						<div data-testid="part-info" className="info">
							<h2>{part.label}</h2>
							<dl>
								<dt>Semantic ID</dt>
								<dd>{part.semanticId}</dd>
								<dt>Role / subsystem</dt>
								<dd>{part.subsystem}</dd>
								<dt>Representation</dt>
								<dd>{part.representationSource}</dd>
								<dt>Dimensions</dt>
								<dd>{part.dimensions.join(" × ")} mm</dd>
								<dt>Verification</dt>
								<dd>{part.verificationState}</dd>
								<dt>Parent</dt>
								<dd>{part.parentAssembly}</dd>
								<dt>Connectors</dt>
								<dd>
									{assembly?.connectors
										.filter((c) => c.semanticId === part.semanticId)
										.map((c) => c.connectorId)
										.join(", ") || "none"}
								</dd>
							</dl>
							<button onClick={() => view.current?.inspect(part.semanticId)}>
								Inspect component
							</button>
						</div>
					) : (
						<p>Click a part to inspect graph-backed engineering metadata.</p>
					)}
					<h3>Assembly parts</h3>
					<div className="part-list">
						{assembly?.parts.map((item) => (
							<button key={item.semanticId} onClick={() => choose(item.semanticId)}>
								{item.label}<small>{item.semanticId}</small>
							</button>
						))}
					</div>
					<h3>Scene metrics</h3>
					<small>
						{Math.round(metrics.triangles || 0)} triangles · first CAD{" "}
						{Math.round(metrics.firstMechanicalMs || 0)} ms · assembly{" "}
						{Math.round(metrics.assemblyMs || 0)} ms
					</small>
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
