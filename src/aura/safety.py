from __future__ import annotations

from pathlib import Path

from .models import ActionRequest, RiskLevel


class SafetyLayer:
    HIGH_RISK_ACTIONS = {
        "send_email",
        "purchase_item",
        "delete_path",
        "publish_post",
    }

    def classify(self, action: str) -> RiskLevel:
        if action in self.HIGH_RISK_ACTIONS:
            return RiskLevel.high
        return RiskLevel.low

    def requires_confirmation(self, request: ActionRequest) -> bool:
        return request.risk == RiskLevel.high

    def requires_path_confirmation(
        self,
        action: str,
        path: str,
        workspace_root: Path,
    ) -> bool:
        """Require approval before modifying an existing file outside AURA."""
        if action not in {"create_file", "write_text_file"}:
            return False
        target = Path(path).expanduser().resolve()
        root = workspace_root.resolve()
        try:
            target.relative_to(root)
            return False
        except ValueError:
            return target.exists()
