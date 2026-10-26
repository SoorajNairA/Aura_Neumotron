import * as THREE from "three";
import {RoomEnvironment} from "three/examples/jsm/environments/RoomEnvironment.js";

type ThumbPart={semanticId:string;family?:string;visualKind?:string;dimensions:number[]};

// Renders one 3/4 studio thumbnail per family with a shared offscreen renderer. Any failure returns {} and
// the UI falls back to family icons; the main scene is never touched.
export function renderThumbnails(parts:ThumbPart[],build:(part:ThumbPart)=>THREE.Object3D|null,size=160):Record<string,string>{
 if((window as any).__auraDisableThumbnails)return {};
 const unique=new Map<string,ThumbPart>();for(const part of parts){const key=part.family||"";if(key&&!unique.has(key))unique.set(key,part)}
 const result:Record<string,string>={};let renderer:THREE.WebGLRenderer|undefined;
 try{
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,preserveDrawingBuffer:true});renderer.setSize(size,size);renderer.setPixelRatio(1);
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;
  const pmrem=new THREE.PMREMGenerator(renderer),environment=pmrem.fromScene(new RoomEnvironment(),.04).texture;pmrem.dispose();
  const camera=new THREE.PerspectiveCamera(30,1,.1,4000);camera.up.set(0,0,1);
  for(const [family,part] of unique){
   const model=build(part);if(!model)continue;
   const scene=new THREE.Scene();scene.environment=environment;scene.add(new THREE.HemisphereLight(0xffffff,0xd9d2c5,.7));
   const key=new THREE.DirectionalLight(0xffffff,1.4);key.position.set(-1,-1.4,2);scene.add(key,model);
   const box=new THREE.Box3().setFromObject(model),center=box.getCenter(new THREE.Vector3()),radius=box.getBoundingSphere(new THREE.Sphere()).radius||10;
   const distance=radius/Math.sin(THREE.MathUtils.degToRad(camera.fov/2))*1.05;
   camera.position.copy(center).add(new THREE.Vector3(.75,-1,.75).normalize().multiplyScalar(distance));camera.lookAt(center);
   renderer.render(scene,camera);result[family]=renderer.domElement.toDataURL("image/png");
   model.traverse(object=>{const mesh=object as THREE.Mesh;mesh.geometry?.dispose();const material=mesh.material;(Array.isArray(material)?material:material?[material]:[]).forEach(item=>item.dispose())});
  }
  environment.dispose();
 }catch{return {}}
 finally{renderer?.dispose();renderer?.forceContextLoss()}
 return result;
}
