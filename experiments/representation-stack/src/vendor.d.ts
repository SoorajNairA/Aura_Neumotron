declare module "cascade-core" {
  export class CascadeEngine {
    constructor(options: { workerUrl: string })
    init(): Promise<void>
    evaluate(code: string, options?: { maxDeviation?: number; guiState?: Record<string, unknown> }): Promise<unknown>
    dispose(): void
  }
}
