import * as THREE from "three"
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js"
import type { CadResult } from "./cad"
import type { RepresentationArtifact, SemanticId } from "./domain"

const COLORS=[0x2dd4bf,0x60a5fa,0xf59e0b]
export class RepresentationScene {
  private scene=new THREE.Scene(); private camera:THREE.PerspectiveCamera; private renderer:THREE.WebGLRenderer; private controls:OrbitControls
  private raycaster=new THREE.Raycaster(); private pointer=new THREE.Vector2(); private nodes=new Map<SemanticId,THREE.Object3D>(); private originals=new Map<SemanticId,THREE.Vector3>()
  private selected?:SemanticId; private hovered?:THREE.Mesh; private animation=0
  constructor(private host:HTMLElement,private onSelect:(id:SemanticId)=>void){
    this.scene.background=new THREE.Color(0x07111f); this.scene.up.set(0,0,1)
    this.camera=new THREE.PerspectiveCamera(45,host.clientWidth/host.clientHeight,.1,2000); this.camera.up.set(0,0,1)
    this.renderer=new THREE.WebGLRenderer({antialias:true}); this.renderer.setPixelRatio(Math.min(devicePixelRatio,2)); this.renderer.setSize(host.clientWidth,host.clientHeight); host.appendChild(this.renderer.domElement)
    this.controls=new OrbitControls(this.camera,this.renderer.domElement); this.resetCamera()
    this.scene.add(new THREE.HemisphereLight(0xffffff,0x172554,2.5)); const key=new THREE.DirectionalLight(0xffffff,3); key.position.set(100,-80,150); this.scene.add(key)
    const grid=new THREE.GridHelper(300,30,0x334155,0x172033); grid.rotateX(Math.PI/2); this.scene.add(grid)
    this.renderer.domElement.addEventListener("pointermove",e=>this.pick(e,false)); this.renderer.domElement.addEventListener("click",e=>this.pick(e,true)); addEventListener("resize",()=>this.resize()); this.loop()
  }
  addCad(result:CadResult,index:number):RepresentationArtifact {
    const geometry=new THREE.BufferGeometry(); const positions:number[]=[]; const normals:number[]=[]; let vertexOffset=0; const indices:number[]=[]
    for(const face of result.mesh.faces){positions.push(...face.vertex_coord); normals.push(...face.normal_coord); indices.push(...face.tri_indexes.map(i=>i+vertexOffset)); vertexOffset+=face.vertex_coord.length/3}
    geometry.setAttribute("position",new THREE.Float32BufferAttribute(positions,3)); geometry.setAttribute("normal",new THREE.Float32BufferAttribute(normals,3)); geometry.setIndex(indices); geometry.computeBoundingBox()
    const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:COLORS[index],roughness:.45,metalness:.1})); const pos=new THREE.Vector3(index*78-70,0,index===1?5:0); mesh.position.copy(pos)
    this.register(result.input.semanticId,mesh,pos,{...result.artifact,dimensionsMm:this.dimensions(geometry.boundingBox!) }); return mesh.userData.artifact
  }
  addProxy(id:SemanticId,label:string,position:[number,number,number],shape:"pump"|"driver"|"catalogue"="driver"){
    const geometry=shape==="catalogue"?new THREE.TorusGeometry(11,4,16,48):shape==="pump"?new THREE.CylinderGeometry(12,12,28,32):new THREE.BoxGeometry(22,18,8,2,2,2)
    if(shape==="pump") geometry.rotateX(Math.PI/2)
    const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0xa78bfa,wireframe:false})); const pos=new THREE.Vector3(...position)
    this.register(id,mesh,pos,{semanticId:id,label,source:"proxy",status:"proxy",triangles:geometry.index?geometry.index.count/3:geometry.attributes.position.count/3,generationMs:0,dimensionsMm:this.dimensions(new THREE.Box3().setFromBufferAttribute(geometry.attributes.position as THREE.BufferAttribute))})
  }
  private register(id:SemanticId,node:THREE.Object3D,pos:THREE.Vector3,artifact:RepresentationArtifact){node.name=id;node.userData.semanticId=id;node.userData.artifact=artifact;node.traverse(o=>{o.userData.semanticId=id;o.userData.semanticRoot=node});this.nodes.set(id,node);this.originals.set(id,pos.clone());this.scene.add(node)}
  select(id:SemanticId){this.selected=id;this.nodes.forEach((node,key)=>node.traverse(o=>{if(o instanceof THREE.Mesh)(o.material as THREE.MeshStandardMaterial).emissive.setHex(key===id?0x2563eb:0)}));this.onSelect(id)}
  isolate(selected:boolean){this.nodes.forEach((node,id)=>node.visible=!selected||id===this.selected)}
  explode(amount:number){this.nodes.forEach((node,id)=>{const base=this.originals.get(id)!;const direction=base.clone().normalize();node.position.copy(base).addScaledVector(direction,amount*55)})}
  resetCamera(){this.camera.position.set(150,-190,130);this.controls?.target.set(0,0,25);this.controls?.update()}
  artifact(id?:SemanticId){return id?this.nodes.get(id)?.userData.artifact as RepresentationArtifact:undefined}
  ids(){return [...this.nodes.keys()]}
  private pick(event:PointerEvent,commit:boolean){const rect=this.renderer.domElement.getBoundingClientRect();this.pointer.set(((event.clientX-rect.left)/rect.width)*2-1,-((event.clientY-rect.top)/rect.height)*2+1);this.raycaster.setFromCamera(this.pointer,this.camera);const hit=this.raycaster.intersectObjects([...this.nodes.values()],true)[0]?.object as THREE.Mesh|undefined;if(this.hovered&&this.hovered!==hit)(this.hovered.material as THREE.MeshStandardMaterial).emissiveIntensity=1;if(hit){this.hovered=hit;(hit.material as THREE.MeshStandardMaterial).emissiveIntensity=2;if(commit)this.select(hit.userData.semanticId)}}
  private dimensions(box:THREE.Box3):[number,number,number]{const v=new THREE.Vector3();box.getSize(v);return [v.x,v.y,v.z]}
  private resize(){if(!this.host.clientWidth)return;this.camera.aspect=this.host.clientWidth/this.host.clientHeight;this.camera.updateProjectionMatrix();this.renderer.setSize(this.host.clientWidth,this.host.clientHeight)}
  private loop=()=>{this.animation=requestAnimationFrame(this.loop);this.controls.update();this.renderer.render(this.scene,this.camera)}
  dispose(){cancelAnimationFrame(this.animation);this.renderer.dispose();this.controls.dispose()}
}
