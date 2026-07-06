from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .model import EngineeringEntity, EngineeringGraph, EntityKind, Relationship, Revision


def graph_to_dict(graph: EngineeringGraph) -> dict[str, Any]:
    return {
        "schema_version": graph.schema_version,
        "project_id": graph.project_id,
        "entities": [asdict(graph.entities[key]) for key in sorted(graph.entities)],
        "relationships": [asdict(graph.relationships[key]) for key in sorted(graph.relationships)],
        "revisions": [asdict(revision) for revision in graph.revisions],
    }


def graph_from_dict(payload: dict[str, Any]) -> EngineeringGraph:
    entities = {
        item["id"]: EngineeringEntity(
            id=item["id"], kind=EntityKind(item["kind"]), name=item["name"],
            parent_id=item.get("parent_id"), metadata=dict(item.get("metadata", {})),
            source_refs=tuple(item.get("source_refs", ())),
            verification_status=item.get("verification_status", "conceptual"),
            representation_refs=tuple(item.get("representation_refs", ())),
        )
        for item in payload.get("entities", [])
    }
    relationships = {
        item["id"]: Relationship(
            id=item["id"], source_id=item["source_id"], target_id=item["target_id"],
            type=item["type"], metadata=dict(item.get("metadata", {})),
        )
        for item in payload.get("relationships", [])
    }
    graph = EngineeringGraph(
        project_id=payload["project_id"], schema_version=payload.get("schema_version", "1.0"),
        entities=entities, relationships=relationships,
        revisions=[Revision(**item) for item in payload.get("revisions", [])],
    )
    graph.validate()
    return graph


def dumps(graph: EngineeringGraph, *, indent: int | None = 2) -> str:
    return json.dumps(graph_to_dict(graph), indent=indent, sort_keys=True)


def loads(value: str) -> EngineeringGraph:
    return graph_from_dict(json.loads(value))


def save(graph: EngineeringGraph, path: Path) -> None:
    path.write_text(dumps(graph) + "\n", encoding="utf-8")


def load(path: Path) -> EngineeringGraph:
    return loads(path.read_text(encoding="utf-8"))
