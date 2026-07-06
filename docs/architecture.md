# AURA Architecture

## Product boundary

AURA is an AI Engineering Workspace built around four domain boundaries:

```text
Structured project request
        |
        v
Planner --proposes--> GraphPatch
        |
        v
Verification --accepts/modifies/rejects
        |
        v
Engineering Graph --commits--> Revision
        |
        v
Workspace --emits--> UI or narration adapters
```

Infrastructure supplies model providers, persistence, voice, registered tools,
desktop actions, configuration, and diagnostics. Infrastructure does not decide
engineering project state.

## Planner

`aura.planner` owns validated request and proposal schemas. The deterministic
service currently produces a minimal initial project hierarchy, relationships,
representation request, verification request, and graph patch. It does not
write files, call a GUI, execute tools, or mark its proposal verified.

`PlannerAgent` remains as a compatibility export for the old assistant path.

## Verification

`aura.verification` validates planner schemas, entity references, project
cardinality, and permitted patch operations. It owns categorical states:

- `tool_verified`
- `source_verified`
- `cross_checked`
- `estimated`
- `conceptual`
- `stale`
- `failed`
- `unsupported`

Current checks prove schema/reference correctness only. They do not claim CAD,
circuit, simulation, catalogue, or physical engineering validation.

## Engineering Graph

`aura.engineering_graph` contains frontend-independent immutable entities and
relationships, mutable graph state, graph patches, revision records, JSON
serialization, and deterministic lookup. It imports no GUI, voice, model,
desktop, or legacy domain implementation.

## Workspace

`aura.workspace` commits only accepted Verification results and emits typed,
GUI-independent events. Current event consumers can subscribe and unsubscribe
without loading QML. A future web workspace can consume the same boundary.

## Infrastructure

`aura.infrastructure` defines narrow boundaries for model providers, graph
persistence, voice interaction, registered tool execution, and desktop actions.
Existing implementations are being adapted incrementally to avoid rewriting
working functionality.

## Compatibility runtime

The current Windows application still runs through `AuraSupervisor`. It owns
voice, conversation, safe tools, memory, project templates, and UI callbacks.
This is transitional compatibility architecture and will be thinned gradually.

Normal supervisor construction no longer imports Unreal. Unreal registration is
explicitly opt-in through the legacy boundary.

## Dependency rules

- Engineering Graph imports no Planner, Verification, Workspace, UI, or infrastructure backend.
- Planner proposes but does not commit or verify.
- Verification may inspect and transform proposals but does not present them.
- Workspace commits verified patches and publishes state changes.
- Voice may provide input and narrate committed events; it does not mutate graph state.
- Arbitrary shell execution is not a supported tool boundary.
