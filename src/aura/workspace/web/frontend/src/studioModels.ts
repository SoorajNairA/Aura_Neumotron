import * as THREE from "three";
import {RoundedBoxGeometry} from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import {J2,J3} from "./pinout";
import {anchor,Label,silkscreen} from "./silkscreen";

// Realistic procedural models for the qualified ESP32 fan workflow. Coordinates: z up, part centred on the
// origin, footprint matching the planner's dimensions so assembly layout and wiring endpoints are preserved.
type StudioPart={semanticId:string;family?:string;visualKind?:string;dimensions:number[];studio?:boolean};
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
 boardWhite:{color:0xf1eee6,roughness:.7},boardShade:{color:0xd9d4c8,roughness:.8},hole:{color:0x2b2b2b,roughness:.9},
 railRed:{color:0xc8372d,roughness:.5},railBlue:{color:0x2457b8,roughness:.5},
 relayBlue:{color:0x1f5fbf,roughness:.35,clearcoat:.5},relayText:{color:0xe8eef6,roughness:.6},servoBlue:{color:0x2c5fb3,roughness:.45,transmission:.1},
 fresnel:{color:0xf4f2ec,roughness:.35,transmission:.25,thickness:1},connectorWhite:{color:0xf2efe6,roughness:.5},ldr:{color:0xc9763a,roughness:.4},
 leadBrown:{color:0x5a3a22,roughness:.5},leadOrange:{color:0xe07a1f,roughness:.5},
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

// A pin header: pins at 2.54 mm along Y, first name at +Y, each tip marked as a wire anchor and labelled on the board.
function header(b:Builder,x:number,top:number,names:string[],labels?:Label[],labelSide=1,tipZ=top+4){
 const n=names.length;b.box([2.5,2.54*n,2.5],"plastic",[x,0,top+1.25]);
 names.forEach((name,i)=>{const y=((n-1)/2-i)*2.54;b.box([.64,.64,4],"gold",[x,y,top+2]);anchor(b.group,name,[x,y,tipZ]);
  labels?.push({text:name,x:x+labelSide*2,y,size:1.1,align:labelSide>0?"left":"right"})});
}
const scaleText=(w:number,l:number)=>Math.max(.8,Math.min(1.4,Math.min(w,l)/14));

function esp32(part:StudioPart){
 const b=new Builder(),[w0,l0,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4));
 // Model along the long axis (Y), then turn it to match the planned footprint.
 const w=Math.min(w0,l0),l=Math.max(w0,l0),pinLength=Math.min(6,h*.45),pcbZ=-h/2+pinLength+.8,top=pcbZ+.8;
 b.box([w,l,1.6],"pcbBlack",[0,0,pcbZ],.6);
 const moduleLength=Math.min(25.5,l*.5),moduleY=l/2-moduleLength/2-.4,moduleWidth=Math.min(18,w*.58);
 b.box([moduleWidth,moduleLength,.8],"pcbBlue",[0,moduleY,top+.4],.3);
 b.box([moduleWidth*.9,moduleLength*.68,2.2],"shield",[0,moduleY-moduleLength*.14,top+1.9],.4);
 // Antenna meander at the module end.
 for(let i=0;i<5;i++)b.box([moduleWidth*.8,.35,.1],"gold",[0,l/2-1.6-i*1.1,top+.85]);
 // DevKitC headers (pinout.ts): 19 pins per side at 2.54 mm, pin 1 at the antenna end; J2 left, J3 right.
 const labels:Label[]=[],seen:Record<string,number>={},pinX=w/2-1.5;
 for(const [side,names] of [[-1,J2],[1,J3]] as const){
  const x=side*pinX;b.box([2.5,19*2.54,2.5],"plastic",[x,0,pcbZ-2.05]);
  names.forEach((name,i)=>{
   const y=(9-i)*2.54;
   b.mesh(new THREE.BoxGeometry(.64,.64,pinLength+1.6),"gold",[x,y,-h/2+(pinLength+1.6)/2]);
   b.cyl(.85,.12,"gold",[x,y,top+.06]);
   seen[name]=(seen[name]||0)+1;anchor(b.group,seen[name]>1?`${name}.${seen[name]}`:name,[x,y,top+.12]);
   labels.push({text:name,x:x-side*1.3,y,size:1,align:side<0?"left":"right"});
  });
 }
 b.box([7.5,5.2,2.6],"tin",[0,-l/2+2.4,top+1.3],.4);
 for(const side of[-1,1]){b.box([3.4,3.4,1.4],"plastic",[side*(w/2-6),-l/2+6,top+.7],.3);b.cyl(.9,.5,"button",[side*(w/2-6),-l/2+6,top+1.6])}
 b.box([5,5,1],"chip",[0,-l*.18,top+.5],.2);b.box([3,2.4,1.2],"chip",[-w*.22,-l*.05,top+.6],.2);b.box([1.2,.8,.6],"ledRed",[w*.25,-l*.12,top+.3]);
 labels.push({text:"ESP32-DevKitC",x:0,y:-l*.32,size:1.6},{text:"EN",x:-(w/2-6),y:-l/2+8.6,size:1},{text:"BOOT",x:w/2-6,y:-l/2+8.6,size:1},
  {text:"J2",x:-(w/2-4.2),y:l/2-1.6,size:1},{text:"J3",x:w/2-4.2,y:l/2-1.6,size:1});
 silkscreen(b.group,w,l,top,labels);
 if(w0>l0)b.group.rotation.z=Math.PI/2;
 return b.group;
}

function ds18b20(part:StudioPart){
 const b=new Builder(),[w,l,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4)),pcbZ=-h/2+.8,top=pcbZ+.8,labels:Label[]=[];
 b.box([w,l,1.6],"pcbGreen",[0,0,pcbZ],.5);
 // TO-92 body: a flat-faced half cylinder standing on three legs.
 const body=b.mesh(new THREE.CylinderGeometry(2.4,2.4,4.8,24,1,false,0,Math.PI),"plastic",[w*.12,0,top+2.6+2.4]);body.rotation.x=Math.PI/2;
 b.box([4.8,.2,4.8],"plastic",[w*.12,0,top+2.6+2.4]);
 for(const x of[-1.27,0,1.27])b.cyl(.25,2.8,"tin",[w*.12+x,0,top+1.4]);
 header(b,-w/2+2,top,["VCC","DAT","GND"],labels);
 b.box([2,1.2,.6],"resistorBody",[w*.1,-l*.32,top+.3]);b.box([1.2,.8,.5],"ledRed",[w*.32,l*.3,top+.25]);
 labels.push({text:"DS18B20",x:w*.12,y:l*.36,size:scaleText(w,l)},{text:"4.7k",x:w*.1,y:-l*.32+1.6,size:.8});
 silkscreen(b.group,w,l,top,labels);
 return b.group;
}

function mosfetModule(part:StudioPart){
 const b=new Builder(),[w,l,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4)),pcbZ=-h/2+.8,top=pcbZ+.8,s=Math.min(1,(h-1.6)/12),labels:Label[]=[];
 b.box([w,l,1.6],"pcbGreen",[0,0,pcbZ],.5);
 // TO-220 MOSFET with a finned heatsink.
 b.box([10,4.5,9*s],"chip",[-w*.05,l*.05,top+4.5*s],.3);
 b.box([12,2,12*s],"heatsink",[-w*.05,l*.05+3.4,top+6*s],.2);
 for(let i=0;i<6;i++)b.box([1,5,11*s],"heatsink",[-w*.05-5+i*2,l*.05+6.4,top+5.5*s]);
 // Four-way screw terminal: supply in (V+, V-) and switched load out (OUT+, OUT-).
 const tx=w/2-5.5,ty=-l*.1,rows=[["V+",5.7],["V-",1.9],["OUT+",-1.9],["OUT-",-5.7]] as const;
 b.box([10,15.2,10*s],"terminal",[tx,ty,top+5*s],.6);
 for(const [name,dy] of rows){b.cyl(1.4,.6,"tin",[tx,ty+dy,top+10*s+.3]);anchor(b.group,name,[tx,ty+dy,top+10*s+.6]);labels.push({text:name,x:tx-5.6,y:ty+dy,size:1,align:"right"})}
 header(b,-w/2+2,top,["IN","VCC","GND"],labels);
 b.box([1.2,.8,.5],"ledRed",[-w*.2,-l*.32,top+.25]);b.box([2,1.2,.6],"resistorBody",[-w*.05,-l*.32,top+.3]);
 labels.push({text:"MOSFET",x:-w*.05,y:-l*.42,size:scaleText(w,l)});
 silkscreen(b.group,w,l,top,labels);
 return b.group;
}

function powerModule(part:StudioPart){
 const b=new Builder(),[w,l,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4)),pcbZ=-h/2+.8,top=pcbZ+.8,labels:Label[]=[];
 b.box([w,l,1.6],"pcbGreen",[0,0,pcbZ],.6);
 b.box([9,7.4,3.2],"tin",[-w/2+4.2,0,top+1.6],1.2);
 b.box([6,6,4],"inductor",[w*.05,l*.15,top+2],.6);
 for(const [x,y] of [[w*.25,l*.2],[w*.25,-l*.2]] as [number,number][]){b.cyl(3,6,"capacitor",[x,y,top+3]);b.cyl(3.05,.4,"tin",[x,y,top+6.1])}
 b.box([4,4,1],"chip",[w*.05,-l*.22,top+.5],.2);
 header(b,w/2-2,top,["+","-"],labels,-1);
 b.box([1.2,.8,.5],"ledRed",[-w*.1,-l*.35,top+.25]);
 labels.push({text:"5V OUT",x:w/2-8,y:-l*.38,size:scaleText(w,l)},{text:"USB-C",x:-w/2+4.2,y:-l*.38,size:1});
 silkscreen(b.group,w,l,top,labels);
 return b.group;
}

function axial(part:StudioPart,kind:"resistor"|"diode"){
 const b=new Builder(),[w]=part.dimensions.map(x=>Math.max(Number(x)||10,3));
 const bodyLength=Math.min(kind==="resistor"?4.4:5.5,w*.6),radius=kind==="resistor"?1.3:1.4;
 b.cyl(.25,w,"tin",[0,0,0],"x");
 b.cyl(radius,bodyLength,kind==="resistor"?"resistorBody":"diodeBody",[0,0,0],"x");
 const bands=kind==="resistor"?["bandYellow","bandViolet","bandRed","gold"]:["bandSilver"];
 bands.forEach((band,i)=>b.cyl(radius+.05,.45,band,[kind==="resistor"?-bodyLength*.32+i*bodyLength*.2:bodyLength*.36,0,0],"x"));
 // Diode cathode is the banded (+X) end.
 anchor(b.group,"A",[-w/2,0,0]);anchor(b.group,kind==="resistor"?"B":"K",[w/2,0,0]);
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
 // Supply terminals at the back of the base: red +, black -.
 for(const [name,dx,kind] of [["+",-3,"bandRed"],["-",3,"plastic"]] as const){b.cyl(1.4,2.4,kind,[w*.3+dx,l/2+1.2,-h/2+baseH*.5],"y");anchor(b.group,name,[w*.3+dx,l/2+2.4,-h/2+baseH*.5])}
 return b.group;
}

// 830-point solderless breadboard at nominal standard size: 63 columns of 2×5 terminal holes either side of a
// centre channel, and four 50-hole power rails (red +, blue −) in groups of five. Holes are one instanced mesh.
function breadboard(part:StudioPart){
 const b=new Builder(),[w,l,h]=part.dimensions.map(x=>Math.max(Number(x)||10,4)),top=h/2,p=2.54;
 b.box([w,l,h],"boardWhite",[0,0,0],1);
 b.box([w-4,2.4,1.2],"boardShade",[0,0,top-.55]);
 const holes:Vec[]=[];
 for(let c=0;c<63;c++)for(const side of[-1,1])for(let r=0;r<5;r++)holes.push([(c-31)*p,side*(p*1.5+r*p),top]);
 for(const side of[-1,1])for(const rail of[0,1])for(let i=0;i<50;i++)holes.push([(i-24.5)*p+(Math.floor(i/5)-4.5)*p,side*(p*1.5+4*p+5.5+rail*p),top]);
 const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,.6),b.mat("hole"),holes.length);mesh.name="breadboard-holes";
 holes.forEach((at,i)=>mesh.setMatrixAt(i,new THREE.Matrix4().makeTranslation(...at)));mesh.instanceMatrix.needsUpdate=true;b.group.add(mesh);
 for(const side of[-1,1])for(const [rail,kind] of[[0,"railBlue"],[1,"railRed"]] as const)b.box([w-12,.5,.12],kind,[0,side*(p*1.5+4*p+5.5+rail*p+(rail?1:-1)*1.6),top+.05]);
 // Power rail ends on the +Y side: red + (outer), blue - (inner).
 anchor(b.group,"+",[-w/2+8,p*1.5+4*p+5.5+p,top]);anchor(b.group,"-",[-w/2+8,p*1.5+4*p+5.5,top]);
 silkscreen(b.group,w,l,top+.05,[{text:"+",x:-w/2+3.5,y:p*1.5+5*p+5.5,size:2.2},{text:"−",x:-w/2+3.5,y:p*1.5+4*p+5.5,size:2.2},{text:"830",x:w/2-8,y:0,size:1.6}]);
 return b.group;
}

// Module models are drawn at typical proportions, then fitted to the catalogue size so layout and wiring stay exact.
function fitted(group:THREE.Group,part:StudioPart){
 const [w,l,h]=part.dimensions.map(x=>Math.max(Number(x)||10,1)),box=new THREE.Box3().setFromObject(group),size=box.getSize(new THREE.Vector3()),centre=box.getCenter(new THREE.Vector3());
 group.scale.set(w/size.x,l/size.y,h/size.z);group.position.set(-centre.x*w/size.x,-centre.y*l/size.y,-centre.z*h/size.z);
 const outer=new THREE.Group();outer.add(group);return outer;
}

function relayModule(part:StudioPart){
 const b=new Builder(),labels:Label[]=[];b.box([50,26,1.6],"pcbBlue",[0,0,.8],.5);
 b.box([19,15.5,15.5],"relayBlue",[2,0,1.6+7.75],.6);b.box([12,1,1],"relayText",[2,-7.8,12],.2);
 b.box([7.5,15,10],"terminal",[19,0,1.6+5],.5);
 for(const [name,y] of [["NC",5],["COM",0],["NO",-5]] as const){b.cyl(1.6,.6,"tin",[19,y,11.9]);anchor(b.group,name,[19,y,12.2]);labels.push({text:name,x:14.6,y,size:1.3,align:"right"})}
 header(b,-22,1.6,["VCC","GND","IN"],labels);
 b.box([3,2,1.2],"chip",[-13,6,2.2]);b.box([1.2,.8,.5],"ledRed",[-13,-7,1.85]);b.box([2,1.2,.6],"resistorBody",[-15,-3,1.9]);b.box([2.5,1.4,1],"diodeBody",[-10,-2,2.1]);
 labels.push({text:"RELAY 5V",x:2,y:-10.8,size:1.6});
 silkscreen(b.group,50,26,1.6,labels);
 return fitted(b.group,part);
}
function led(part:StudioPart){
 const b=new Builder(),r=2.3;
 // The anode leg is the longer one.
 b.cyl(.25,4,"tin",[-1.27,0,2]);b.cyl(.25,4.6,"tin",[1.27,0,2.3]);
 b.cyl(r*1.08,.9,"ledRed",[0,0,4.45]);b.cyl(r,4.4,"ledRed",[0,0,4.9+2.2]);
 const lens=b.mesh(new THREE.SphereGeometry(r,24,12,0,Math.PI*2,0,Math.PI/2),"ledRed",[0,0,9.3]);lens.rotation.x=Math.PI/2;lens.name="led-lens";
 anchor(b.group,"A",[1.27,0,0]);anchor(b.group,"K",[-1.27,0,.6]);
 return fitted(b.group,part);
}
function pushButton(part:StudioPart){
 const b=new Builder();for(const x of[-4.5,4.5])for(const y of[-3.2,3.2])b.box([.8,.4,3.5],"tin",[x,y,1.75]);
 b.box([12,12,3.5],"plastic",[0,0,3.5+1.75],.6);b.box([12.2,12.2,.4],"shield",[0,0,7.2]);
 b.cyl(3.5,3,"button",[0,0,7.4+1.5]);
 anchor(b.group,"1",[-4.5,-3.2,0]);anchor(b.group,"2",[4.5,-3.2,0]);
 return fitted(b.group,part);
}
function servo(part:StudioPart){
 const b=new Builder();b.box([22.5,12,22.7],"servoBlue",[0,0,11.35],.6);
 b.box([32,12,2.5],"servoBlue",[0,0,15.9]);for(const x of[-14,14])b.cyl(1,2.6,"plastic",[x,0,15.9]);
 b.cyl(5.9,4,"servoBlue",[-5.4,0,22.7+2]);b.cyl(2.4,3.2,"servoBlue",[1.5,0,22.7+1.6]);b.cyl(2.3,3,"heatsink",[-5.4,0,26.7+1.5]);
 const horn=new THREE.Group();horn.name="servo-horn";horn.position.set(-5.4,0,29.7);b.group.add(horn);
 b.box([24,3.6,1.6],"button",[0,0,.8],.8,horn);b.cyl(3.4,1.6,"button",[0,0,.8],"z",horn);
 // Three-wire lead ending in a plug: brown GND, red V+, orange signal.
 b.box([4,6,1],"plastic",[11.5,-6,3]);
 for(const [name,x,kind] of [["GND",10.3,"leadBrown"],["V+",11.5,"bandRed"],["SIG",12.7,"leadOrange"]] as const){b.box([.8,2,.8],kind,[x,-9.4,3]);anchor(b.group,name,[x,-10.4,3])}
 return fitted(b.group,part);
}
function pirSensor(part:StudioPart){
 const b=new Builder(),labels:Label[]=[];b.box([32,24,1.6],"pcbGreen",[0,0,.8],.5);
 b.box([23,23,7],"button",[0,0,1.6+3.5],.4);
 const dome=b.mesh(new THREE.SphereGeometry(11.5,32,16,0,Math.PI*2,0,Math.PI/2),"fresnel",[0,0,8.6]);dome.rotation.x=Math.PI/2;
 for(const y of[-4,4])b.cyl(2,2,"terminal",[13,y,-1]);header(b,-14.5,-4.5,["VCC","OUT","GND"],undefined,1,-4.5);
 return fitted(b.group,part);
}
function soilProbe(part:StudioPart){
 const b=new Builder(),L=98,labels:Label[]=[];
 b.box([L*.78,23,1.6],"pcbBlack",[-L*.11,0,.8],.6);
 const tip=b.mesh(new THREE.CylinderGeometry(11.5,.6,L*.22,3),"pcbBlack",[L*.39,0,.8]);tip.rotation.z=Math.PI/2;tip.scale.set(1,1,.14);
 b.box([L*.5,15,.12],"tin",[0,0,1.66]);b.box([5,5,1.2],"chip",[-L*.33,4,2.2]);b.box([2,1.2,.6],"resistorBody",[-L*.36,-5,1.9]);
 b.box([6,8,4],"connectorWhite",[-L*.46,0,2]);
 for(const [name,y] of [["AOUT",2.54],["VCC",0],["GND",-2.54]] as const){anchor(b.group,name,[-L*.46-3,y,2]);labels.push({text:name,x:-L*.42,y,size:1.3,align:"left"})}
 labels.push({text:"SOIL SENSOR",x:-L*.25,y:-8.5,size:1.8});
 silkscreen(b.group,L*.78,23,1.6,labels,[-L*.11,0]);
 return fitted(b.group,part);
}
function lightSensor(part:StudioPart){
 const b=new Builder(),labels:Label[]=[];b.box([32,14,1.6],"pcbBlack",[0,0,.8],.5);
 for(const y of[-1.5,1.5])b.cyl(.25,3,"tin",[12,y,3.1]);b.cyl(2.6,1.6,"ldr",[12,0,5.4],"x");
 b.box([6.5,6.5,4.5],"terminal",[2,0,1.6+2.25],.4);b.cyl(1.4,1,"shield",[2,0,6.6]);
 b.box([4.5,4,1.4],"chip",[-6,2,2.3]);b.box([1.2,.8,.5],"ledRed",[-6,-4,1.85]);header(b,-14.5,1.6,["VCC","GND","DO","AO"],labels);
 labels.push({text:"LDR",x:12,y:-4.6,size:1.2});
 silkscreen(b.group,32,14,1.6,labels);
 return fitted(b.group,part);
}
// Any other small sensor: a labelled breakout with a chip, header and mounting holes, not a model of the real board.
function sensorBreakout(part:StudioPart){
 const b=new Builder(),labels:Label[]=[];b.box([20,16,1.6],"pcbBlue",[0,0,.8],.6);
 b.box([4,4,1],"chip",[2,0,2.1]);b.box([1.6,.8,.5],"capacitor",[6,4,1.85]);b.box([2,1.2,.6],"resistorBody",[6,-4,1.9]);
 for(const y of[-5.5,5.5])b.ring(1.2,.35,"tin",[7.5,y,1.65]);header(b,-8.5,1.6,["VCC","GND","SCL","SDA"],labels);
 silkscreen(b.group,20,16,1.6,labels);
 return fitted(b.group,part);
}

const SENSOR_BREAKOUTS=new Set(["environmental_sensor","distance_sensor","orientation_sensor","gas_sensor","humidity_sensor","pressure_sensor"]);
function studioBuilder(family:string,kind:string):((part:StudioPart)=>THREE.Group)|null{
 if(family==="microcontroller_board")return !kind||kind.includes("esp32")?esp32:null;
 const builders:Record<string,(part:StudioPart)=>THREE.Group>={temperature_sensor:ds18b20,mosfet_driver:mosfetModule,fan:deskFan,low_voltage_power_source:powerModule,
  resistor:part=>axial(part,"resistor"),flyback_diode:part=>axial(part,"diode"),breadboard,relay_module:relayModule,indicator:led,switch:pushButton,servo,
  motion_sensor:pirSensor,soil_moisture_sensor:soilProbe,light_sensor:lightSensor};
 return builders[family]??(SENSOR_BREAKOUTS.has(family)?sensorBreakout:null);
}
export const hasStudioModel=(family?:string,kind?:string)=>studioBuilder(family||"",kind||"")!==null;

export function buildStudioModel(part:StudioPart):THREE.Group|null{
 if(!part.studio)return null;
 return studioBuilder(part.family||"",part.visualKind||"")?.(part)??null;
}
