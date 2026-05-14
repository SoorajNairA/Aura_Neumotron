from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, memory_dir: Path) -> None:
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.user_file = self.memory_dir / "user_profile.json"
        self.projects_file = self.memory_dir / "projects.json"
        self.logs_file = self.memory_dir / "action_log.jsonl"

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data: Any) -> None:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_user_profile(self) -> dict[str, Any]:
        return self._read_json(self.user_file, {})

    def update_user_profile(self, updates: dict[str, Any]) -> dict[str, Any]:
        profile = self.get_user_profile()
        profile.update(updates)
        self._write_json(self.user_file, profile)
        return profile

    def get_projects(self) -> dict[str, Any]:
        return self._read_json(self.projects_file, {})

    def upsert_project(self, key: str, project_data: dict[str, Any]) -> None:
        projects = self.get_projects()
        projects[key] = project_data
        self._write_json(self.projects_file, projects)

    def append_log(self, event: dict[str, Any]) -> None:
        with self.logs_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=True) + "\n")

    def read_recent_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.logs_file.exists():
            return []

        rows: list[dict[str, Any]] = []
        with self.logs_file.open("r", encoding="utf-8") as f:
            for line in f:
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)

        if limit <= 0:
            return rows
        return rows[-limit:]

    def get_project_by_keyword(self, terms: list[str]) -> dict | None:
        """Return the first project whose key contains any of the given terms.

        Returns None if no projects exist or no keyword matches.
        """
        if not terms:
            return None
        projects = self.get_projects()
        terms_lower = [t.lower() for t in terms if t]
        for key, data in projects.items():
            key_lower = key.lower()
            if any(t in key_lower for t in terms_lower):
                return data
        return None
