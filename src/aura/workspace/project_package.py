"""Project ZIP package: export a stored project and validate an untrusted package on import.

Format version 1 (see docs/superpowers/specs/2026-10-29-layout-file-menu-wiring-edit-design.md, section 2).
Nothing from the environment, model profiles or key store is ever read here; a package holds only project data.
"""
from __future__ import annotations

import io
import json
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aura.engineering_graph.model import EngineeringGraph
from aura.engineering_graph.patches import GraphPatch
from aura.engineering_graph.serialization import graph_from_dict, graph_to_dict, patch_from_dict, patch_to_dict

from .representations import RepresentationRecord

PACKAGE_FORMAT = "aura-project"
PACKAGE_VERSION = 1
MAX_PACKAGE_BYTES = 20 * 1024 * 1024  # compressed upload, and the total of all members once unzipped
MAX_LAYOUT_BYTES = 1024 * 1024
PLANNING_MODES = {"deterministic_test", "deterministic_fallback", "live_model"}
KNOWN_MEMBERS = frozenset({
    "manifest.json", "graph.json", "project.json", "layout.json", "control-rules.json",
    "hardware-evidence.json", "firmware/main.ino", "firmware/edit.json",
})
EMPTY_LAYOUT: dict[str, Any] = {"parts": {}, "wires": {}, "labels": {}}


class PackageError(Exception):
    """A package (or layout) problem with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass
class PackageContents:
    manifest: dict[str, Any]
    graph: EngineeringGraph
    objective: str
    planning_mode: str
    fallback_reason: str | None
    status: str
    had_representations: bool
    latest_patch: GraphPatch | None
    latest_verification: dict[str, Any] | None
    layout: dict[str, Any] | None
    control_rules: dict[str, Any] | None
    hardware_evidence: dict[str, Any] | None
    firmware_edit: dict[str, str] | None


def validate_layout(value: Any) -> dict[str, Any]:
    """Wiring layout: an object whose parts, wires and labels (when present) are objects. Extra keys are kept."""
    if not isinstance(value, dict):
        raise PackageError("INVALID_LAYOUT", "Layout must be an object")
    layout = dict(value)
    for field in ("parts", "wires", "labels"):
        item = layout.setdefault(field, {})
        if not isinstance(item, dict):
            raise PackageError("INVALID_LAYOUT", f"Layout field '{field}' must be an object")
    if len(json.dumps(layout, separators=(",", ":"))) > MAX_LAYOUT_BYTES:
        raise PackageError("INVALID_LAYOUT", "Layout is too large")
    return layout


def rewrite_project_id(value: Any, old: str, new: str) -> Any:
    """Copy of a JSON structure with every string (and key) equal to the old project id replaced."""
    if isinstance(value, str):
        return new if value == old else value
    if isinstance(value, list):
        return [rewrite_project_id(item, old, new) for item in value]
    if isinstance(value, dict):
        return {(new if key == old else key): rewrite_project_id(item, old, new) for key, item in value.items()}
    return value


def slug(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40].strip("-")
    return text or "project"


def _dump(value: Any) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")


def build_zip(application: Any, project_id: str) -> bytes:
    """Restorable ZIP of one stored project. Raises KeyError when the project does not exist."""
    repository = application.repository
    record = repository.get_project(project_id)
    if record is None:
        raise KeyError(project_id)
    now = datetime.now(timezone.utc)
    root = record.graph.entities.get(record.graph.project_id)
    members: dict[str, bytes] = {}
    members["manifest.json"] = _dump({
        "format": PACKAGE_FORMAT, "version": PACKAGE_VERSION, "exportedAt": now.isoformat(),
        "projectId": project_id, "objective": record.objective, "name": root.name if root else None,
        "appVersion": os.getenv("AURA_VERSION", "0.1.0"),
    })
    members["graph.json"] = _dump(graph_to_dict(record.graph))
    revisions = repository.list_revisions(project_id)
    latest = ({"revision": revisions[-1]["revision"], "patch": patch_to_dict(revisions[-1]["patch"]),
               "verification": revisions[-1]["verification"]} if revisions else None)
    representations = []
    for item in record.representations:
        parsed = RepresentationRecord.from_dict(item)
        representations.append({"type": parsed.type.value, "semanticIds": list(parsed.semantic_ids), "status": parsed.status.value})
    members["project.json"] = _dump({
        "objective": record.objective, "planningMode": record.planning_mode, "fallbackReason": record.fallback_reason,
        "status": record.status, "representations": representations, "latestRevision": latest,
    })
    stored_layout = repository.get_layout(project_id)
    members["layout.json"] = _dump(stored_layout["layout"] if stored_layout else EMPTY_LAYOUT)
    rules = repository.get_control_rules(project_id)
    if rules is not None:
        members["control-rules.json"] = _dump(rules)
    evidence = repository.get_hardware_evidence(project_id)
    if evidence is not None:
        members["hardware-evidence.json"] = _dump(evidence)
    firmware_source = getattr(application, "firmware_source", None)
    source = firmware_source(project_id, record.graph) if firmware_source is not None else None
    if source:
        members["firmware/main.ino"] = source.encode("utf-8")
    edit = repository.get_firmware_edit(project_id)
    if edit:
        members["firmware/edit.json"] = _dump({"block": edit["block"], "revisionId": edit["revisionId"]})
    buffer = io.BytesIO()
    stamp = now.timetuple()[:6]
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def _parse(name: str, raw: bytes, error_code: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise PackageError(error_code, f"{name} is not valid JSON") from exc


def _object(name: str, value: Any, error_code: str = "CORRUPT_GRAPH") -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PackageError(error_code, f"{name} must be a JSON object")
    return value


def _unsafe(name: str) -> bool:
    return (name not in KNOWN_MEMBERS or "\\" in name or name.startswith("/") or ":" in name
            or any(part in {"", ".", ".."} for part in name.split("/")))


def read_zip(data: bytes) -> PackageContents:
    """Validate an untrusted package. Raises PackageError; never writes anything."""
    if len(data) > MAX_PACKAGE_BYTES:
        raise PackageError("TOO_LARGE", "Project file is larger than the 20 MB limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = archive.infolist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError, EOFError) as exc:
        raise PackageError("NOT_A_ZIP", "The file is not a ZIP archive") from exc
    names = [info.filename for info in infos]
    if "manifest.json" not in names:
        raise PackageError("NOT_AN_AURA_PROJECT", "The ZIP has no manifest.json; it is not an AURA project")
    for name in names:
        if _unsafe(name):
            raise PackageError("UNSAFE_PATH", f"The ZIP contains a path that is not allowed: {name[:80]!r}")
    if len(names) != len(set(names)):
        raise PackageError("UNSAFE_PATH", "The ZIP lists the same path twice")
    for info in infos:
        if info.flag_bits & 0x1:
            raise PackageError("NOT_A_ZIP", "Encrypted ZIP files are not supported")
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise PackageError("NOT_A_ZIP", "The ZIP uses an unsupported compression method")
    if sum(info.file_size for info in infos) > MAX_PACKAGE_BYTES:
        raise PackageError("TOO_LARGE", "The project is larger than the 20 MB limit once unpacked")
    raw: dict[str, bytes] = {}
    for info in infos:
        try:
            with archive.open(info) as member:
                value = member.read(info.file_size + 1)
        except Exception as exc:  # BadZipFile, zlib.error, NotImplementedError, RuntimeError: all mean a broken archive
            raise PackageError("NOT_A_ZIP", "The ZIP could not be read; it may be damaged") from exc
        if len(value) != info.file_size:
            raise PackageError("NOT_A_ZIP", "The ZIP could not be read; it may be damaged")
        raw[info.filename] = value

    manifest = _object("manifest.json", _parse("manifest.json", raw["manifest.json"], "NOT_AN_AURA_PROJECT"), "NOT_AN_AURA_PROJECT")
    if manifest.get("format") != PACKAGE_FORMAT or "version" not in manifest:
        raise PackageError("NOT_AN_AURA_PROJECT", "manifest.json does not describe an AURA project")
    version = manifest["version"]
    if type(version) is not int or version != PACKAGE_VERSION:
        raise PackageError("UNSUPPORTED_VERSION", f"Project format version {str(version)[:20]} is not supported; this build reads version {PACKAGE_VERSION}")
    for required in ("graph.json", "project.json"):
        if required not in raw:
            raise PackageError("CORRUPT_GRAPH", f"The ZIP has no {required}")

    try:
        graph = graph_from_dict(_object("graph.json", _parse("graph.json", raw["graph.json"], "CORRUPT_GRAPH")))
    except PackageError:
        raise
    except Exception as exc:
        raise PackageError("CORRUPT_GRAPH", f"graph.json is not a valid engineering graph: {str(exc)[:120]}") from exc
    if not graph.revisions:
        raise PackageError("CORRUPT_GRAPH", "graph.json has no committed revision")

    project = _object("project.json", _parse("project.json", raw["project.json"], "CORRUPT_GRAPH"))
    objective = project.get("objective")
    if not isinstance(objective, str) or not objective.strip() or len(objective) > 2000:
        raise PackageError("CORRUPT_GRAPH", "project.json has no valid objective")
    planning_mode = project.get("planningMode", "deterministic_test")
    if planning_mode not in PLANNING_MODES:
        raise PackageError("CORRUPT_GRAPH", "project.json has an unknown planning mode")
    fallback = project.get("fallbackReason")
    if fallback is not None and (not isinstance(fallback, str) or len(fallback) > 2000):
        raise PackageError("CORRUPT_GRAPH", "project.json has an invalid fallback reason")
    status = project.get("status", "ready_with_limitations")
    if not isinstance(status, str) or len(status) > 64:
        raise PackageError("CORRUPT_GRAPH", "project.json has an invalid status")
    representations = project.get("representations", [])
    if not isinstance(representations, list):
        raise PackageError("CORRUPT_GRAPH", "project.json representations must be a list")
    patch: GraphPatch | None = None
    verification: dict[str, Any] | None = None
    latest = project.get("latestRevision")
    if latest is not None:
        try:
            patch = patch_from_dict(_object("latestRevision.patch", _object("latestRevision", latest).get("patch")))
            verification = _object("latestRevision.verification", latest.get("verification"))
        except PackageError:
            raise
        except Exception as exc:
            raise PackageError("CORRUPT_GRAPH", "project.json latest revision is not valid") from exc

    layout = None
    if "layout.json" in raw:
        try:
            layout = validate_layout(_parse("layout.json", raw["layout.json"], "CORRUPT_GRAPH"))
        except PackageError as exc:
            raise PackageError("CORRUPT_GRAPH", f"layout.json is not valid: {exc.message}") from exc
    rules = None
    if "control-rules.json" in raw:
        rules = _object("control-rules.json", _parse("control-rules.json", raw["control-rules.json"], "CORRUPT_GRAPH"))
        if (not isinstance(rules.get("rules", []), list) or not all(isinstance(item, dict) for item in rules.get("rules", []))
                or not isinstance(rules.get("bindings", {}), dict)):
            raise PackageError("CORRUPT_GRAPH", "control-rules.json has an invalid rule list")
    evidence = None
    if "hardware-evidence.json" in raw:
        evidence = _object("hardware-evidence.json", _parse("hardware-evidence.json", raw["hardware-evidence.json"], "CORRUPT_GRAPH"))
    edit = None
    if "firmware/edit.json" in raw:
        value = _object("firmware/edit.json", _parse("firmware/edit.json", raw["firmware/edit.json"], "CORRUPT_GRAPH"))
        block, revision_id = value.get("block"), value.get("revisionId")
        if not (isinstance(block, str) and 0 < len(block) <= 20000 and isinstance(revision_id, str) and 0 < len(revision_id) <= 128):
            raise PackageError("CORRUPT_GRAPH", "firmware/edit.json is not valid")
        edit = {"block": block, "revisionId": revision_id}
    return PackageContents(manifest, graph, objective, planning_mode, fallback, status, bool(representations),
        patch, verification, layout, rules, evidence, edit)
