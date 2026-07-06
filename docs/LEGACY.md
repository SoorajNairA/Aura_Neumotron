# Legacy Systems

Legacy means retained for compatibility or evaluation, not part of the new AURA
product architecture.

| System | Status | Reusable content |
|---|---|---|
| Unreal professional domain | Opt-in; excluded from normal startup | Project scanning, Blueprint analysis, documentation lookup, issue classification |
| TITAN validation | Opt-in historical evaluation | Generic benchmark result patterns may be extracted later |
| ExecutiveAgent | Active compatibility path | Project templates, assumptions, artifact verification |
| SoftwareDirector | Active compatibility path | Project lifecycle and deterministic checks |
| ComputerOperator | Optional compatibility path | Controlled application and desktop adapters |
| DomainManager | Transitional; Unreal disabled by default | Plugin registration concepts |
| ChiefArchitect | Standalone legacy experiment | Static source analysis and reporting |
| OperatorQuality | Legacy support for ComputerOperator | Recovery/observability data |

`aura.legacy.unreal.create_unreal_domain()` is the explicit Unreal loader.
Direct imports such as `aura.unreal_domain` remain temporarily compatible.

No large subsystem has been deleted during this migration stage. Removal should
occur only after useful deterministic code is extracted, old tests are marked
legacy, persisted formats are accounted for, and the compatibility runtime no
longer imports the subsystem.

The historical Jarvis, TITAN, OMEGA, ORACLE, CORTEX, ASCENSION, and specialist
terminology does not describe supported core architecture.
