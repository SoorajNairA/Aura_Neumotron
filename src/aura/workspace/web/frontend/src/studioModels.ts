import * as THREE from "three";
import {RoundedBoxGeometry} from "three/examples/jsm/geometries/RoundedBoxGeometry.js";

// Realistic procedural models for the qualified ESP32 fan workflow. Coordinates: z up, part centred on the
// origin, footprint matching the planner's dimensions so assembly layout and wiring endpoints are preserved.
type StudioPart={semanticId:string;family?:string;visualKind?:string;dimensions:number[]};
type Vec=[number,number,number];

const FINISH:Record<string,THREE.MeshPhysicalMaterialParameters>={
 pcbBlack:{color:0x1d2124,roughness:.45,clearcoat:.6,clearcoatRoughness:.3},
 pcbGreen:{color:0x1e6b47,roughness:.4,clearcoat:.7,clearcoatRoughness:.3},
 pcbBlue:{color:0x1b2a3a,roughness:.45,clearcoat:.5},
 gold:{color:0xc9a24a,metalness:1,roughness:.3},
 tin:{color:0xc8ccd0,metalness:1,roughness:.35},
 shield:{color:0xd3d6d9,metalness:.95,roughness:.25},
 plastic:{color:0x141618,roughness:.6},
 chip:{color:0x111315,roughness:.5},
 heatsink:{color:0x1b1d20,metalness:.6,roughness:.45},
 terminal:{color:0x1f5fbf,roughness:.45,clearcoat:.4},
 ledRed:{color:0xd2342a,roughness:.3,emissive:0x5a0d08},
 capacitor:{color:0x2b2f33,roughness:.4,clearcoat:.4},
 inductor:{color:0x3a3f44,roughness:.7},
 fanBody:{color:0x5d8a70,roughness:.45,clearcoat:.35,clearcoatRoughness:.4},
 fanGrille:{color:0x4b7360,metalness:.2,roughness:.4},
 fanInner:{color:0x2f4a3d,roughness:.7},
 fanBlade:{color:0x6f9a80,roughness:.5,side:THREE.DoubleSide},
 fanBase:{color:0xece4d3,roughness:.5,clearcoat:.25},
 button:{color:0xd9d2c3,roughness:.4},
 resistorBody:{color:0xd8c39a,roughness:.55},
 diodeBody:{color:0x18191b,roughness:.4},
 bandYellow:{color:0xe3b505,roughness:.5},bandViolet:{color:0x7b3fa0,roughness:.5},bandRed:{color:0xc8372d,roughness:.5},bandSilver:{color:0xc0c4c8,metalness:.8,roughness:.3},
};

class Builder{
 readonly group=new THREE.Group();
 private cache=new Map<string,THREE.Material>();
 // Materials are per model: selection highlighting mutates them per part.
 mat(kind:string){let material=this.cache.get(kind);if(!material){material=new THREE.MeshPhysicalMaterial(FINISH[kind]);this.cache.set(kind,material)}return material}
 mesh(geometry:THREE.BufferGeometry,kind:string,at:Vec,parent:THREE.Object3D=this.group){const mesh=new THREE.Mesh(geometry,this.mat(kind));mesh.position.set(...at);mesh.castShadow=true;mesh.receiveShadow=true;parent.add(mesh);return mesh}
 box(size:Vec,kind:string,at:Vec,radius=0,parent?:THREE.Object3D){const r=Math.min(radius,Math.min(...size)/2-.01);return this.mesh(r>0?new RoundedBoxGeometry(size[0],size[1],size[2],2,r):new THREE.BoxGeometry(...size),kind,at,parent)}
 cyl(radius:number,length:number,kind:string,at:Vec,axis:"x"|"y"|"z"="z",parent?:THREE.Object3D,segments=24){const mesh=this.mesh(new THREE.CylinderGeometry(radius,radius,length,segments),kind,at,parent);if(axis==="x")mesh.rotation.z=Math.PI/2;if(axis==="z")mesh.rotation.x=Math.PI/2;return mesh}
 ring(radius:number,tube:number,kind:string,at:Vec,parent?:THREE.Object3D){const mesh=this.mesh(new THREE.TorusGeometry(radius,tube,10,48),kind,at,parent);mesh.rotation.x=Math.PI/2;return mesh}
}

function esp32(part:StudioPart){
 const b=new Builder(),[w0,l0,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4));
 // Model along the long axis (Y), then turn it to match the planned footprint.
 const w=Math.min(w0,l0),l=Math.max(w0,l0),pinLength=Math.min(6,h*.45),pcbZ=-h/2+pinLength+.8,top=pcbZ+.8;
 b.box([w,l,1.6],"pcbBlack",[0,0,pcbZ],.6);
 const moduleLength=Math.min(25.5,l*.5),moduleY=l/2-moduleLength/2-.4;
 b.box([w*.64,moduleLength,.8],"pcbBlue",[0,moduleY,top+.4],.3);
 b.box([w*.58,moduleLength*.68,2.2],"shield",[0,moduleY-moduleLength*.14,top+1.9],.4);
 for(let i=0;i<5;i++)b.box([w*.5,.35,.1],"gold",[0,l/2-1.6-i*1.1,top+.85]);
 for(const side of[-1,1]){
  b.box([2.5,l*.92,2.5],"plastic",[side*(w/2-1.5),-.5,pcbZ-2.05]);
  for(let i=0;i<19;i++){const y=-l*.46+i*(l*.92/18);b.mesh(new THREE.BoxGeometry(.64,.64,pinLength+1.6),"gold",[side*(w/2-1.5),y-.5,-h/2+(pinLength+1.6)/2])}
 }
 b.box([7.5,5.2,2.6],"tin",[0,-l/2+2.4,top+1.3],.4);
 for(const side of[-1,1]){b.box([3.4,3.4,1.4],"plastic",[side*(w/2-6),-l/2+6,top+.7],.3);b.cyl(.9,.5,"button",[side*(w/2-6),-l/2+6,top+1.6])}
 b.box([5,5,1],"chip",[0,-l*.18,top+.5],.2);b.box([3,2.4,1.2],"chip",[-w*.22,-l*.05,top+.6],.2);b.box([1.2,.8,.6],"ledRed",[w*.25,-l*.12,top+.3]);
 if(w0>l0)b.group.rotation.z=Math.PI/2;
 return b.group;
}

function ds18b20(part:StudioPart){
 const b=new Builder(),[w,l,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4)),pcbZ=-h/2+.8,top=pcbZ+.8;
 b.box([w,l,1.6],"pcbGreen",[0,0,pcbZ],.5);
 // TO-92 body: a flat-faced half cylinder standing on three legs.
 const body=b.mesh(new THREE.CylinderGeometry(2.4,2.4,4.8,24,1,false,0,Math.PI),"plastic",[w*.12,0,top+2.6+2.4]);body.rotation.x=Math.PI/2;
 b.box([4.8,.2,4.8],"plastic",[w*.12,0,top+2.6+2.4]);
 for(const x of[-1.27,0,1.27])b.cyl(.25,2.8,"tin",[w*.12+x,0,top+1.4]);
 b.box([2.5,7.6,2.5],"plastic",[-w/2+2,0,top+1.25]);
 for(const y of[-2.54,0,2.54])b.box([.64,.64,4],"gold",[-w/2+2,y,top+2]);
 b.box([2,1.2,.6],"resistorBody",[w*.1,-l*.32,top+.3]);b.box([1.2,.8,.5],"ledRed",[w*.32,l*.3,top+.25]);
 return b.group;
}

function mosfetModule(part:StudioPart){
 const b=new Builder(),[w,l,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4)),pcbZ=-h/2+.8,top=pcbZ+.8,s=Math.min(1,(h-1.6)/12);
 b.box([w,l,1.6],"pcbGreen",[0,0,pcbZ],.5);
 // TO-220 MOSFET with a finned heatsink.
 b.box([10,4.5,9*s],"chip",[-w*.05,l*.05,top+4.5*s],.3);
 b.box([12,2,12*s],"heatsink",[-w*.05,l*.05+3.4,top+6*s],.2);
 for(let i=0;i<6;i++)b.box([1,5,11*s],"heatsink",[-w*.05-5+i*2,l*.05+6.4,top+5.5*s]);
 b.box([10,7.6,10*s],"terminal",[w/2-5.5,-l*.1,top+5*s],.6);
 for(const y of[-1.9,1.9])b.cyl(1.4,.6,"tin",[w/2-5.5,-l*.1+y,top+10*s+.3]);
 b.box([2.5,7.6,2.5],"plastic",[-w/2+2,0,top+1.25]);
 for(const y of[-2.54,0,2.54])b.box([.64,.64,4],"gold",[-w/2+2,y,top+2]);
 b.box([1.2,.8,.5],"ledRed",[-w*.2,-l*.32,top+.25]);b.box([2,1.2,.6],"resistorBody",[-w*.05,-l*.32,top+.3]);
 return b.group;
}

function powerModule(part:StudioPart){
 const b=new Builder(),[w,l,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4)),pcbZ=-h/2+.8,top=pcbZ+.8;
 b.box([w,l,1.6],"pcbGreen",[0,0,pcbZ],.6);
 b.box([9,7.4,3.2],"tin",[-w/2+4.2,0,top+1.6],1.2);
 b.box([6,6,4],"inductor",[w*.05,l*.15,top+2],.6);
 for(const [x,y] of [[w*.25,l*.2],[w*.25,-l*.2]] as [number,number][]){b.cyl(3,6,"capacitor",[x,y,top+3]);b.cyl(3.05,.4,"tin",[x,y,top+6.1])}
 b.box([4,4,1],"chip",[w*.05,-l*.22,top+.5],.2);
 b.box([2.5,7.6,2.5],"plastic",[w/2-2,0,top+1.25]);
 for(const y of[-2.54,0,2.54])b.box([.64,.64,4],"gold",[w/2-2,y,top+2]);
 b.box([1.2,.8,.5],"ledRed",[-w*.1,-l*.35,top+.25]);
 return b.group;
}

function axial(part:StudioPart,kind:"resistor"|"diode"){
 const b=new Builder(),[w]=part.dimensions.map(x=>Math.max(Number(x)||10,3));
 const bodyLength=Math.min(kind==="resistor"?4.4:5.5,w*.6),radius=kind==="resistor"?1.3:1.4;
 b.cyl(.25,w,"tin",[0,0,0],"x");
 b.cyl(radius,bodyLength,kind==="resistor"?"resistorBody":"diodeBody",[0,0,0],"x");
 const bands=kind==="resistor"?["bandYellow","bandViolet","bandRed","gold"]:["bandSilver"];
 bands.forEach((band,i)=>b.cyl(radius+.05,.45,band,[kind==="resistor"?-bodyLength*.32+i*bodyLength*.2:bodyLength*.36,0,0],"x"));
 return b.group;
}

function deskFan(part:StudioPart){
 const b=new Builder(),[w,l,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4));
 const baseH=h*.16,depth=l*.62,housingH=h*.82,housingZ=-h/2+baseH+housingH/2,front=-depth/2,radius=Math.min(w,housingH)*.38;
 b.box([w*.92,l,baseH],"fanBase",[0,0,-h/2+baseH/2],Math.min(5,baseH/2));
 b.cyl(Math.max(2,h*.035),1.2,"button",[w*.3,-l/2-.3,-h/2+baseH/2],"y");
 // Housing: a rounded frame with a circular opening so the blades are visible, closed by a rear panel.
 const corner=Math.min(12,w*.14),shape=new THREE.Shape();
 shape.moveTo(-w/2+corner,-housingH/2);shape.lineTo(w/2-corner,-housingH/2);shape.quadraticCurveTo(w/2,-housingH/2,w/2,-housingH/2+corner);shape.lineTo(w/2,housingH/2-corner);shape.quadraticCurveTo(w/2,housingH/2,w/2-corner,housingH/2);
 shape.lineTo(-w/2+corner,housingH/2);shape.quadraticCurveTo(-w/2,housingH/2,-w/2,housingH/2-corner);shape.lineTo(-w/2,-housingH/2+corner);shape.quadraticCurveTo(-w/2,-housingH/2,-w/2+corner,-housingH/2);
 const opening=new THREE.Path();opening.absarc(0,0,radius+1,0,Math.PI*2,true);shape.holes.push(opening);
 const frame=b.mesh(new THREE.ExtrudeGeometry(shape,{depth:depth-2,bevelEnabled:true,bevelThickness:1,bevelSize:1.2,bevelSegments:3,curveSegments:48}),"fanBody",[0,front+1,housingZ]);
 // Extrude from the front face toward the back (+Y).
 frame.rotation.set(-Math.PI/2,0,0);frame.position.set(0,front+1,housingZ);
 b.box([w*.96,2,housingH*.96],"fanBody",[0,depth/2-1,housingZ],1);
 b.cyl(radius,1,"fanInner",[0,depth/2-2.6,housingZ],"y",undefined,48);
 // Rotor: hub plus nine twisted blades, spun about the fan axis (Y) by the simulation.
 const rotor=new THREE.Group();rotor.name="fan-rotor";rotor.position.set(0,front+depth*.35,housingZ);b.group.add(rotor);
 b.cyl(radius*.24,6,"fanGrille",[0,0,0],"y",rotor);
 for(let i=0;i<9;i++){const angle=i*Math.PI*2/9,blade=b.box([radius*.72,1.2,radius*.32],"fanBlade",[Math.cos(angle)*radius*.58,0,-Math.sin(angle)*radius*.58],.5,rotor);blade.name="fan-blade";blade.rotation.set(.38,angle,0,"YXZ")}
 // Front grille: rim, concentric rings and spokes.
 b.ring(radius,2.4,"fanGrille",[0,front-.6,housingZ]);
 for(const fraction of[.34,.58,.8])b.ring(radius*fraction,.45,"fanGrille",[0,front-.8,housingZ]);
 for(let i=0;i<12;i++){const angle=i*Math.PI/6,spoke=b.box([radius,.6,.6],"fanGrille",[Math.cos(angle)*radius/2,front-.8,housingZ-Math.sin(angle)*radius/2]);spoke.rotation.y=angle}
 b.cyl(radius*.2,1.4,"fanBody",[0,front-1,housingZ],"y");
 return b.group;
}

export function buildStudioModel(part:StudioPart):THREE.Group|null{
 const family=part.family||"",kind=part.visualKind||"";
 if(family==="microcontroller_board"&&(!kind||kind.includes("esp32")))return esp32(part);
 if(family==="temperature_sensor")return ds18b20(part);
 if(family==="mosfet_driver")return mosfetModule(part);
 if(family==="fan")return deskFan(part);
 if(family==="low_voltage_power_source")return powerModule(part);
 if(family==="resistor")return axial(part,"resistor");
 if(family==="flyback_diode")return axial(part,"diode");
 return null;
}
