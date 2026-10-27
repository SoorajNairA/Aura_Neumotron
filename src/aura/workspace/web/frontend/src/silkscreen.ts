import * as THREE from "three";

type Vec=[number,number,number];
export type Label={text:string;x:number;y:number;size?:number;rotate?:number;align?:CanvasTextAlign};

// Invisible marker at a real pin tip; wires start and end exactly here.
export function anchor(parent:THREE.Object3D,name:string,at:Vec){const marker=new THREE.Object3D();marker.name=`pin:${name}`;marker.position.set(...at);parent.add(marker);return marker}

export function pinAnchors(root:THREE.Object3D):Record<string,THREE.Object3D>{
 const pins:Record<string,THREE.Object3D>={};
 root.traverse(object=>{if(object.name.startsWith("pin:"))pins[object.name.slice(4)]=object});
 return pins;
}

const PX_PER_MM=10;
// White silkscreen printed on a board top: one transparent plane covering the board, text drawn at board millimetres.
// Without a DOM (unit tests) the plane carries only the label list, so tests can read what would be printed.
export function silkscreen(parent:THREE.Object3D,width:number,length:number,z:number,labels:Label[],centre:[number,number]=[0,0]){
 const material=new THREE.MeshBasicMaterial({transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-2});
 if(typeof document!=="undefined"){
  const canvas=document.createElement("canvas");canvas.width=Math.ceil(width*PX_PER_MM);canvas.height=Math.ceil(length*PX_PER_MM);
  const context=canvas.getContext("2d");
  if(context){
   context.fillStyle="#f4f1e8";context.textBaseline="middle";
   for(const label of labels){
    context.save();context.translate((label.x-centre[0]+width/2)*PX_PER_MM,(length/2-(label.y-centre[1]))*PX_PER_MM);context.rotate(-(label.rotate||0));
    context.font=`600 ${Math.round((label.size||1.3)*PX_PER_MM)}px "Cascadia Mono","JetBrains Mono",Consolas,monospace`;context.textAlign=label.align||"center";
    context.fillText(label.text,0,0);context.restore();
   }
   const texture=new THREE.CanvasTexture(canvas);texture.anisotropy=8;texture.colorSpace=THREE.SRGBColorSpace;material.map=texture;
  }
 }
 const plane=new THREE.Mesh(new THREE.PlaneGeometry(width,length),material);
 plane.position.set(centre[0],centre[1],z+.02);plane.name="silkscreen";plane.userData.texts=labels.map(label=>label.text);plane.renderOrder=2;
 parent.add(plane);return plane;
}
