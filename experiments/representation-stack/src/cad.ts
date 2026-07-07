import { CascadeEngine } from "cascade-core"
import type { RepresentationArtifact, RepresentationInput } from "./domain"

export interface CadMeshData { faces: Array<{vertex_coord:number[];normal_coord:number[];tri_indexes:number[];number_of_triangles:number}> }
export interface CadResult { input: RepresentationInput; mesh: CadMeshData; artifact: RepresentationArtifact }

const definitions: Array<RepresentationInput & { code: string }> = [
  { semanticId:"component-reservoir", label:"Lofted reservoir", source:"cascade-core", code:`
    let a=Circle(22,true); let b=Translate([0,0,28],Circle(35,true)); let c=Translate([5,0,62],Circle(27,true)); let d=Translate([12,0,92],Circle(12,true)); Loft([a,b,c,d]);` },
  { semanticId:"component-tube", label:"Swept irrigation tube", source:"cascade-core", code:`
    let profile=Circle(5); let path=BSpline([[0,0,0],[20,0,10],[38,12,28],[48,25,55],[65,30,76]]); Pipe(profile,path);` },
  { semanticId:"component-enclosure", label:"Filleted controller enclosure", source:"cascade-core", code:`
    let body=Box(58,42,20,true); FilletEdges(body,4,Edges(body).ofType("Line").indices());` },
]

const timeout = <T,>(promise: Promise<T>, ms: number) => Promise.race<T>([promise, new Promise<T>((_, reject) => setTimeout(() => reject(new Error(`timed out after ${ms}ms`)), ms))])

export class CadGenerator {
  private engine = new CascadeEngine({ workerUrl: "/cascade-worker.js" })
  async init() { const started=performance.now(); await timeout(this.engine.init(), 15_000); return performance.now()-started }
  async generate(onStatus: (id:string,status:string)=>void): Promise<CadResult[]> {
    const results: CadResult[]=[]
    for (const input of definitions) {
      onStatus(input.semanticId,"pending")
      let lastError: unknown
      for (let attempt=1; attempt<=2; attempt++) {
        const started=performance.now()
        try {
          const output=await timeout(this.engine.evaluate(input.code,{maxDeviation:0.35}),20_000) as {meshData:CadMeshData}
          if (!output.meshData?.faces?.length) throw new Error("CAD engine returned no faces")
          const triangles=output.meshData.faces.reduce((n,f)=>n+f.number_of_triangles,0)
          results.push({input,mesh:output.meshData,artifact:{...input,status:"succeeded",triangles,generationMs:performance.now()-started,dimensionsMm:[0,0,0]}})
          onStatus(input.semanticId,"succeeded"); lastError=undefined; break
        } catch (error) { lastError=error; console.error(`[CAD ${input.semanticId}] attempt ${attempt}`,error) }
      }
      if (lastError) { onStatus(input.semanticId,"failed"); throw lastError }
    }
    return results
  }
  dispose(){this.engine.dispose()}
}
