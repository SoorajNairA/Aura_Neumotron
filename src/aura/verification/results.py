from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aura.engineering_graph.patches import GraphPatch


class VerificationState(str, Enum):
    TOOL_VERIFIED = "tool_verified"
    SOURCE_VERIFIED = "source_verified"
    CROSS_CHECKED = "cross_checked"
    ESTIMATED = "estimated"
    CONCEPTUAL = "conceptual"
    STALE = "stale"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class VerificationDecision(str, Enum):
    ACCEPT = "accept"
    MODIFY = "modify"
    REJECT = "reject"


@dataclass(frozen=True)
class VerificationResult:
    decision: VerificationDecision
    state: VerificationState
    reasons: tuple[str, ...]
    patch: GraphPatch | None

    @property
    def accepted(self) -> bool:
        return self.decision in {VerificationDecision.ACCEPT, VerificationDecision.MODIFY}
