# Vertex Planner decision

Selected `gemini-3.1-flash-lite` on the managed global Vertex publisher endpoint. ADC is used locally; no endpoint, key file, GPU, or provisioned throughput is created.

The August 2026 discovery excluded Gemini 2.5 because its published retirement is October 16, 2026. Compared on the six-project corpus, structured output, and one modification:

| Model | Valid | First pass | Mean / p50 / observed p95 | Modification | Estimated slice cost |
|---|---:|---:|---|---|---:|
| gemini-3.1-flash-lite | 6/6 | 6/6 | 3.12 / 2.24 / 7.74 s | pass, 1.84 s | $0.00285 |
| gemini-3-flash-preview | 6/6 | 6/6 | 9.72 / 8.05 / 20.14 s | pass, 22.93 s | $0.00617 |
| gemini-3.1-pro-preview | 6/6 | 6/6 | 7.18 / 6.29 / 11.58 s | pass, 4.21 s | $0.04838 |

Flash-Lite had equivalent schema and invariant reliability, lowest latency, and lowest cost. Production timeout is 20 seconds. Vertex transient failures retry once and then use the deterministic Planner; authentication failures are actionable startup errors. Sources: Google Cloud Vertex model lifecycle, release notes, thinking configuration, and pricing documentation.
