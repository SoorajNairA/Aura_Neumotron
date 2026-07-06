from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class RepresentationType(str, Enum):
    PLACEHOLDER = "placeholder"
    MECHANICAL_3D = "mechanical_3d"
    CATALOG_3D = "catalog_3d"
    CIRCUIT_SCHEMATIC = "circuit_schematic"
    PCB = "pcb"
    SYSTEM_DIAGRAM = "system_diagram"
    CODE_PREVIEW = "code_preview"
    DOCUMENT = "document"


class RepresentationStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    CONCEPTUAL = "conceptual"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RepresentationRequest:
    component_id: str
    type: RepresentationType
    status: RepresentationStatus = RepresentationStatus.PENDING
    artifact_id: str | None = None
    fallback_type: RepresentationType = RepresentationType.PLACEHOLDER

    def to_dict(self) -> dict:
        return {"componentId": self.component_id, "type": self.type.value,
                "status": self.status.value, "artifactId": self.artifact_id,
                "fallbackType": self.fallback_type.value}
