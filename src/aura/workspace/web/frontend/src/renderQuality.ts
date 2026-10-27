// Studio effects (ambient occlusion) only where they run smoothly; everything still works in "basic".
export type Quality="high"|"basic";
export const qualityFor=({webgl2,reducedMotion,slow}:{webgl2:boolean;reducedMotion:boolean;slow:boolean}):Quality=>webgl2&&!reducedMotion&&!slow?"high":"basic";

export class SlowFrames{
 private times:number[]=[];
 constructor(private size=10){}
 add(ms:number){this.times.push(ms);if(this.times.length>this.size)this.times.shift()}
 // Slow when a full window of frames has a median above 33 ms (under 30 fps).
 get slow(){if(this.times.length<this.size)return false;const sorted=[...this.times].sort((a,b)=>a-b);return sorted[Math.floor((sorted.length-1)/2)]>33}
}
