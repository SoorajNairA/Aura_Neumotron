from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from aura.engineering_graph.interfaces import component_interfaces
from aura.engineering_graph.model import EngineeringEntity, EngineeringGraph, EntityKind, Relationship, dimension_mm
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation, apply_patch
from aura.verification.catalogue import CATALOGUE, CATALOGUE_VERSION


class ModificationError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class ModificationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["ATTACH_TO_INTERFACE", "SCALE_DIMENSIONS", "SET_PARAMETER", "REPLACE_COMPONENT", "UNSUPPORTED"]
    targetSemanticId: str
    summary: str = Field(min_length=1, max_length=240)
    rationale: str = Field(min_length=1, max_length=1200)
    referenceSemanticId: Optional[str]
    referenceInterface: Optional[str]
    targetInterface: Optional[str]
    scalePercent: Optional[float]
    preserveDimensions: list[Literal["width", "length", "height"]]
    parameterKey: Optional[str]
    parameterValueJson: Optional[str]
    componentDefinitionId: Optional[str]


class LiveModificationPlanner:
    """Converts natural language to a bounded graph edit and validates every model reference."""

    def __init__(self, provider: Any) -> None:
        self.provider, self.last_metadata = provider, {}

    def propose(self, graph: EngineeringGraph, base: int, ids: list[str], request: str, mode: str = "automatic") -> ModificationProposal:
        if base != len(graph.revisions):
            raise ModificationError("stale_revision", "The project changed. Reload it and try the edit again.", 409)
        if len(ids) != 1 or ids[0] not in graph.entities or graph.get(ids[0]).kind is not EntityKind.COMPONENT:
            raise ModificationError("unsupported_target", "Select one component before requesting an edit.")
        target = graph.get(ids[0])
        components = []
        for entity in graph.find(kind=EntityKind.COMPONENT):
            parameters = entity.metadata.get("parameters", {})
            interfaces = component_interfaces(_family(entity), _dimensions(entity), parameters)
            components.append({
                "id": entity.id, "name": entity.name, "family": _family(entity),
                "functionalRoles": parameters.get("functional_roles", []),
                "controlledAxisIds": parameters.get("controlled_axis_ids", []),
                "drivenAxisIds": parameters.get("driven_axis_ids", []),
                "dimensions": entity.metadata.get("dimensions", {}),
                "editableParameterKeys": sorted(key for key, value in parameters.items() if isinstance(value, (str, int, float, bool))),
                "physicalInterfaces": [{"name": item.name, "kind": item.kind, "compatibleWith": list(item.compatible)} for item in interfaces],
            })
        connections = {item.id: item for item in graph.find(kind=EntityKind.CONNECTION)}
        mechanical = []
        for relation in graph.relationships.values():
            if relation.type not in {"mechanical", "fixed", "revolute", "hinge"}:
                continue
            connection = connections.get(str(relation.metadata.get("connection_id", "")))
            mechanical.append({
                "relationshipId": relation.id, "sourceId": relation.source_id, "targetId": relation.target_id,
                "sourceInterface": connection.metadata.get("source_interface") if connection else None,
                "targetInterface": connection.metadata.get("target_interface") if connection else None,
            })
        replacements = [{"componentDefinitionId": item.component_definition_id, "manufacturer": item.manufacturer, "partNumber": item.part_number}
                        for item in CATALOGUE if item.family == _family(target)]
        context = {
            "request": request, "selectedSemanticId": target.id, "components": components,
            "existingMechanicalConnections": mechanical, "compatibleReplacementDefinitions": replacements,
            "allowedActions": {
                "ATTACH_TO_INTERFACE": "Mount/move the selected component using listed compatible interfaces on it and another listed component.",
                "SCALE_DIMENSIONS": "Scale selected dimensions by a percentage and optionally preserve named dimensions.",
                "SET_PARAMETER": "Set one listed scalar parameter; encode the primitive new value in parameterValueJson.",
                "REPLACE_COMPONENT": "Choose one compatible replacement definition.",
                "UNSUPPORTED": "Use when no other action represents the request safely.",
            },
        }
        instruction = (
            "Translate the user's engineering edit into exactly one bounded action. Reason from component roles, axis IDs, topology, "
            "and interface semantics; never use keyword substitution and never invent an ID, interface, parameter, dimension, or part. "
            "targetSemanticId must equal selectedSemanticId. For a joint or axis tip, choose the component whose drivenAxisIds identify "
            "that axis and its distal/end interface. ATTACH_TO_INTERFACE endpoints must be mutually compatible. Return UNSUPPORTED when "
            "the result is ambiguous or cannot be represented safely. Return only the response schema."
        )
        error = ""
        result = decision = None
        for attempt in range(2):
            payload = context if not error else {**context, "previousResponseError": error}
            result = self.provider.generate_structured(
                [{"role": "user", "content": json.dumps(payload, separators=(",", ":"), sort_keys=True)}],
                system_prompt=instruction, max_tokens=900, response_schema=ModificationDecision.model_json_schema())
            try:
                decision = ModificationDecision.model_validate_json(result.text)
                break
            except Exception as exc:
                error = f"Return a schema-valid decision: {exc}"
        if decision is None or result is None:
            raise ModificationError("model_modification_invalid", "The edit could not be converted into a valid engineering operation.", 502)
        if decision.targetSemanticId != target.id:
            raise ModificationError("model_modification_invalid", "The proposed edit did not preserve the selected component.", 502)
        if decision.action == "UNSUPPORTED":
            raise ModificationError("modification_not_actionable", decision.rationale)
        self.last_metadata = {
            "source": "structured_model", "repairAttempts": attempt, "firstPassValid": attempt == 0,
            "inputTokens": getattr(result, "input_tokens", None), "outputTokens": getattr(result, "output_tokens", None),
            "totalTokens": getattr(result, "total_tokens", None),
        }
        dispatch = {"ATTACH_TO_INTERFACE": _attach, "SCALE_DIMENSIONS": _scale,
                    "SET_PARAMETER": _set_parameter, "REPLACE_COMPONENT": _replace}
        return dispatch[decision.action](graph, base, target, decision, mode)


@dataclass(frozen=True)
class ModificationProposal:
    proposal_id: str
    base_revision: int
    target_ids: tuple[str, ...]
    summary: str
    mode: str
    operations: tuple[dict[str, Any], ...]
    affected_ids: tuple[str, ...]
    unaffected: tuple[str, ...]
    regenerate: tuple[str, ...]
    verification: dict[str, Any]
    patch: GraphPatch
    preview: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposalId": self.proposal_id, "baseRevision": self.base_revision,
            "targetSemanticIds": list(self.target_ids), "summary": self.summary, "mode": self.mode,
            "operations": list(self.operations), "affectedSemanticIds": list(self.affected_ids),
            "unaffectedAreas": list(self.unaffected), "artifactsToRegenerate": list(self.regenerate),
            "verification": self.verification, "preview": self.preview,
            "assumptions": ["Conceptual geometry requires physical validation"],
        }


def _proposal(graph: EngineeringGraph, base: int, target: EngineeringEntity, decision: ModificationDecision, mode: str,
              operations: list[dict[str, Any]], patch_operations: list[GraphOperation], affected: tuple[str, ...],
              regenerate: tuple[str, ...] = ()) -> ModificationProposal:
    patch = GraphPatch(f"patch-{uuid4().hex}", tuple(patch_operations), decision.summary, graph.current_revision_id)
    from .assembly import engineering_assembly
    candidate = engineering_assembly(apply_patch(graph, patch))
    part = next((item for item in candidate["parts"] if item["semanticId"] == target.id), None)
    preview = ({"semanticId": target.id, "position": part["assembledTransform"]["position"],
                "rotation": part["assembledTransform"].get("rotation", [0, 0, 0, 1]), "dimensions": part["dimensions"]}
               if part else None)
    verification = {"outcome": "pending_graph_verification", "checks": [{"state": "PASSED", "message": "Edit references validated against the current Engineering Graph"}]}
    return ModificationProposal(f"proposal-{uuid4().hex}", base, (target.id,), decision.summary, mode, tuple(operations), affected,
                                ("unrelated subsystems",), regenerate, verification, patch, preview)


def _attach(graph: EngineeringGraph, base: int, target: EngineeringEntity, decision: ModificationDecision, mode: str) -> ModificationProposal:
    reference_id = decision.referenceSemanticId
    if not reference_id or reference_id == target.id or reference_id not in graph.entities or graph.get(reference_id).kind is not EntityKind.COMPONENT:
        raise ModificationError("invalid_attachment_reference", "The placement did not resolve to another current component.")
    reference = graph.get(reference_id)
    reference_interfaces = {item.name: item for item in component_interfaces(_family(reference), _dimensions(reference), reference.metadata.get("parameters", {}))}
    target_interfaces = {item.name: item for item in component_interfaces(_family(target), _dimensions(target), target.metadata.get("parameters", {}))}
    source_interface = reference_interfaces.get(str(decision.referenceInterface or ""))
    target_interface = target_interfaces.get(str(decision.targetInterface or ""))
    if source_interface is None or target_interface is None or target_interface.kind not in source_interface.compatible:
        raise ModificationError("incompatible_attachment_interfaces", "The placement did not resolve to compatible physical interfaces.")
    existing = [relation for relation in graph.relationships.values()
                if relation.type in {"mechanical", "fixed", "revolute", "hinge"} and target.id in {relation.source_id, relation.target_id}]
    if len(existing) > 1:
        raise ModificationError("ambiguous_mechanical_attachment", "This component has multiple structural connections; specify which one should move.")
    occupied = set()
    replacing_ids = {relation.id for relation in existing}
    for relation in graph.relationships.values():
        if relation.id in replacing_ids or relation.type not in {"mechanical", "fixed", "revolute", "hinge"}:
            continue
        connection = graph.entities.get(str(relation.metadata.get("connection_id", "")))
        if connection and connection.kind is EntityKind.CONNECTION:
            occupied.add((relation.source_id, connection.metadata.get("source_interface")))
            occupied.add((relation.target_id, connection.metadata.get("target_interface")))
    if (reference.id, source_interface.name) in occupied:
        raise ModificationError("attachment_interface_in_use", "The selected mounting interface is already occupied by another component.")
    new_value = {"sourceId": reference.id, "targetId": target.id,
                 "sourceInterface": source_interface.name, "targetInterface": target_interface.name}
    if existing:
        relation = existing[0]
        connection_id = str(relation.metadata.get("connection_id", ""))
        connection = graph.entities.get(connection_id)
        if connection is None or connection.kind is not EntityKind.CONNECTION:
            raise ModificationError("mechanical_connection_incomplete", "The current mechanical connection has no editable graph record.")
        old_value = {"sourceId": relation.source_id, "targetId": relation.target_id,
                     "sourceInterface": connection.metadata.get("source_interface"),
                     "targetInterface": connection.metadata.get("target_interface")}
        metadata = dict(connection.metadata) | {
            "source_id": reference.id, "target_id": target.id, "source_interface": source_interface.name,
            "target_interface": target_interface.name, "connection_type": "mechanical"}
        patch_operations = [
            GraphOperation(PatchOperation.UPDATE_RELATIONSHIP, target_id=relation.id,
                           changes={"source_id": reference.id, "target_id": target.id, "type": "mechanical"}),
            GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=connection.id, changes={"metadata": metadata}),
        ]
        operations = [{"operation": "update_mechanical_attachment", "targetId": relation.id, "connectionId": connection.id,
                       "path": "mechanical attachment", "oldValue": old_value, "newValue": new_value}]
    else:
        suffix = uuid4().hex[:10]
        connection_id, relation_id = f"connection-user-mate-{suffix}", f"connection-user-mate-{suffix}-edge"
        metadata = {"source_id": reference.id, "target_id": target.id, "source_interface": source_interface.name,
                    "target_interface": target_interface.name, "connection_type": "mechanical"}
        connection = EngineeringEntity(connection_id, EntityKind.CONNECTION, f"Mount {target.name} to {reference.name}", graph.project_id, metadata)
        relation = Relationship(relation_id, reference.id, target.id, "mechanical", {"connection_id": connection_id})
        patch_operations = [GraphOperation(PatchOperation.ADD_ENTITY, entity=connection), GraphOperation(PatchOperation.ADD_RELATIONSHIP, relationship=relation)]
        operations = [{"operation": "add_mechanical_attachment", "targetId": relation_id, "connectionId": connection_id,
                       "path": "mechanical attachment", "oldValue": None, "newValue": new_value}]
    regenerate = (f"repr-{target.id.removeprefix('component-')}-3d",)
    return _proposal(graph, base, target, decision, mode, operations, patch_operations, (target.id, reference.id), regenerate)


def _scale(graph: EngineeringGraph, base: int, target: EngineeringEntity, decision: ModificationDecision, mode: str) -> ModificationProposal:
    percent = decision.scalePercent
    if percent is None or not -80 <= percent <= 500 or abs(percent) < .01:
        raise ModificationError("invalid_dimension_scale", "Specify a dimension change between -80% and +500%.")
    dimensions = {key: dict(value) for key, value in target.metadata.get("dimensions", {}).items()}
    preserve, operations = set(decision.preserveDimensions), []
    for key in ("width", "length", "height"):
        if key in preserve or key not in dimensions:
            continue
        old = float(dimensions[key]["value"])
        new = round(old * (1 + percent / 100), 3)
        if new <= 0:
            raise ModificationError("invalid_dimension_scale", "The scale would produce a non-positive dimension.")
        dimensions[key]["value"] = new
        operations.append({"operation": "replace_parameter", "path": f"dimensions.{key}.value", "oldValue": old, "newValue": new})
    if not operations:
        raise ModificationError("modification_not_actionable", "The request preserved every available dimension.")
    metadata = dict(target.metadata) | {"dimensions": dimensions}
    patch = [GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=target.id, changes={"metadata": metadata})]
    return _proposal(graph, base, target, decision, mode, operations, patch, (target.id,),
                     (f"repr-{target.id.removeprefix('component-')}-3d",))


def _set_parameter(graph: EngineeringGraph, base: int, target: EngineeringEntity, decision: ModificationDecision, mode: str) -> ModificationProposal:
    parameters, key = dict(target.metadata.get("parameters", {})), str(decision.parameterKey or "")
    if not key or key not in parameters or not isinstance(parameters[key], (str, int, float, bool)):
        raise ModificationError("invalid_parameter_edit", "The edit did not resolve to an existing scalar engineering parameter.")
    try:
        value = json.loads(str(decision.parameterValueJson))
    except Exception as exc:
        raise ModificationError("invalid_parameter_edit", "The requested parameter value was invalid.") from exc
    if not isinstance(value, (str, int, float, bool)) or value == parameters[key]:
        raise ModificationError("invalid_parameter_edit", "The requested parameter value was unchanged or unsupported.")
    old, parameters[key] = parameters[key], value
    metadata = dict(target.metadata) | {"parameters": parameters}
    operation = {"operation": "replace_parameter", "path": f"parameters.{key}", "oldValue": old, "newValue": value}
    patch = [GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=target.id, changes={"metadata": metadata})]
    return _proposal(graph, base, target, decision, mode, [operation], patch, (target.id,))


def _replace(graph: EngineeringGraph, base: int, target: EngineeringEntity, decision: ModificationDecision, mode: str) -> ModificationProposal:
    definition = next((item for item in CATALOGUE if item.component_definition_id == decision.componentDefinitionId), None)
    if definition is None or definition.family != _family(target):
        raise ModificationError("incompatible_component_definition", "The replacement is not a compatible curated component definition.")
    metadata, old = dict(target.metadata), target.metadata.get("component_definition_id")
    metadata["component_definition_id"], metadata["component_definition_version"] = definition.component_definition_id, CATALOGUE_VERSION
    metadata["parameters"] = dict(metadata.get("parameters", {})) | {
        "component_definition_id": definition.component_definition_id, "component_definition_version": CATALOGUE_VERSION}
    dimensions = definition.properties.get("dimensions")
    if dimensions:
        metadata["dimensions"] = {key: {"value": value, "unit": dimensions.unit}
                                  for key, value in zip(("width", "length", "height"), dimensions.value)}
    operation = {"operation": "replace_component_definition", "path": "component_definition_id", "oldValue": old,
                 "newValue": definition.component_definition_id}
    patch = [GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=target.id, changes={"metadata": metadata})]
    return _proposal(graph, base, target, decision, mode, [operation], patch, (target.id,),
                     (f"repr-{target.id.removeprefix('component-')}-3d",))


def _family(entity: EngineeringEntity) -> str:
    return str(entity.metadata.get("family", entity.metadata.get("role", "")))


def _dimensions(entity: EngineeringEntity) -> tuple[float, float, float]:
    values = entity.metadata.get("dimensions", {})
    return tuple(dimension_mm(values[key]) if key in values else float(fallback) for key, fallback in (("width", 45), ("length", 30), ("height", 18)))


# This legacy function is used only by deterministic tests and bounded verification repair.
# Interactive production edits always use LiveModificationPlanner above.
def propose(graph: EngineeringGraph, base: int, ids: list[str], request: str, mode: str = "automatic") -> ModificationProposal:
    if base != len(graph.revisions): raise ValueError("stale_revision")
    if len(ids) != 1 or ids[0] not in graph.entities: raise ValueError("unsupported_target")
    target = graph.get(ids[0]); meta = dict(target.metadata); lower = request.lower(); operations = []
    family = meta.get("family", meta.get("role", "")); regenerate = (); unaffected = ("unrelated subsystems",)
    exact = next((item for item in CATALOGUE if item.component_definition_id.lower() in lower), None)
    if exact:
        compatible_families = {exact.family}
        compatible_families.add({"microcontroller_board": "controller", "small_dc_pump": "water delivery",
                                 "soil_moisture_sensor": "soil sensing"}.get(exact.family, exact.family))
        if family not in compatible_families: raise ValueError("incompatible_component_definition")
        old = meta.get("component_definition_id"); meta["component_definition_id"] = exact.component_definition_id; meta["component_definition_version"] = CATALOGUE_VERSION
        params = dict(meta.get("parameters", {})); params.update(component_definition_id=exact.component_definition_id, component_definition_version=CATALOGUE_VERSION); meta["parameters"] = params
        dimensions = exact.properties.get("dimensions")
        if dimensions: meta["dimensions"] = {key: {"value": value, "unit": dimensions.unit} for key, value in zip(("width", "length", "height"), dimensions.value)}
        summary = f"Upgrade {target.name} to curated {exact.manufacturer} {exact.part_number}"; regenerate = (f"repr-{target.id.removeprefix('component-')}-3d",)
        operations = [{"operation": "replace_component_definition", "path": "component_definition_id", "oldValue": old, "newValue": exact.component_definition_id}]
    elif family == "temperature_sensor" and any(value in lower for value in ("lower", "threshold", "temperature", "earlier")):
        params = dict(meta["parameters"]); old = params.get("threshold_c", 26); params["threshold_c"] = old - 2; meta["parameters"] = params
        summary = "Lower the temperature activation threshold"; operations = [{"operation": "replace_parameter", "path": "parameters.threshold_c", "oldValue": old, "newValue": params["threshold_c"]}]
    elif family in {"container", "reservoir"} and any(value in lower for value in ("larger", "capacity", "size", "width", "depth")):
        dimensions = {key: dict(value) for key, value in meta["dimensions"].items()}
        for key in ("width", "length"):
            old = dimensions[key]["value"]; dimensions[key]["value"] = round(old * 1.2)
            operations.append({"operation": "replace_parameter", "path": f"dimensions.{key}.value", "oldValue": old, "newValue": dimensions[key]["value"]})
        meta["dimensions"] = dimensions; summary = "Increase container capacity while preserving height"
        regenerate = (f"repr-{target.id.removeprefix('component-')}-3d",); unaffected = ("electronics",)
    elif family in {"motor_driver", "relay"} and "mosfet" in lower:
        params = dict(meta["parameters"]); old = params.get("driver_type"); params.update(driver_type="logic-level MOSFET", flyback_protection=True); meta["parameters"] = params
        summary = f"Replace {target.name} with a logic-level MOSFET"; regenerate = (f"repr-{target.id.removeprefix('component-')}-schematic",)
        operations = [{"operation": "replace_parameter", "path": "parameters.driver_type", "oldValue": old, "newValue": params["driver_type"]}]
    elif family in {"small_dc_pump", "pump"} and any(value in lower for value in ("move", "farther", "position")):
        old = meta.get("assembly_offset_mm", [0, 0, 0]); meta["assembly_offset_mm"] = [-35, -45, 0]
        summary = f"Move {target.name} farther from electronics while preserving fluid connections"; regenerate = (f"repr-{target.id.removeprefix('component-')}-3d",)
        operations = [{"operation": "replace_parameter", "path": "assembly_offset_mm", "oldValue": old, "newValue": meta["assembly_offset_mm"]}]
    else: raise ValueError("unsupported_modification")
    patch = GraphPatch(f"patch-{uuid4().hex}", (GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=target.id, changes={"metadata": meta}),), summary, graph.current_revision_id)
    verification = {"outcome": "accepted_with_warnings", "checks": [{"state": "PASSED", "message": "Target and values valid"}]}
    return ModificationProposal(f"proposal-{uuid4().hex}", base, tuple(ids), summary, mode, tuple(operations), (target.id,), unaffected, regenerate, verification, patch)


def inverse_proposal(graph: EngineeringGraph, revision: dict[str, Any]) -> ModificationProposal:
    diff = revision.get("verification", {}).get("diff")
    if not diff or not diff.get("changed"): raise ValueError("nothing_to_undo")
    patch, changed = revision["patch"], diff["changed"]
    added = [item for item in changed if item.get("operation") == "add_component"]
    if added:
        patch_ops = []
        for item in added:
            if item["targetId"] not in graph.entities: raise ValueError("nothing_to_undo")
            if item.get("connectionId"):
                patch_ops += [GraphOperation(PatchOperation.REMOVE_RELATIONSHIP, target_id=f"{item['connectionId']}-edge"),
                              GraphOperation(PatchOperation.REMOVE_ENTITY, target_id=item["connectionId"])]
            patch_ops.append(GraphOperation(PatchOperation.REMOVE_ENTITY, target_id=item["targetId"]))
        # Nets were materialized on commit; drop the ones that would point at removed parts.
        removed = {item["targetId"] for item in added}
        patch_ops += [GraphOperation(PatchOperation.REMOVE_ENTITY, target_id=net.id) for net in graph.entities.values()
                      if net.metadata.get("semantic_type") == "electrical_net"
                      and any(t.get("componentId") in removed for t in net.metadata.get("terminals", []))]
        pins = next((item for item in changed if item.get("path") == "parameters.gpio_map"), None)
        if pins:
            controller = graph.get(pins["targetId"])
            params = dict(controller.metadata.get("parameters", {})) | {"gpio_map": pins["oldValue"]}
            patch_ops.append(GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=controller.id, changes={"metadata": dict(controller.metadata) | {"parameters": params}}))
        inverse = [{**item, "operation": "remove_component", "oldValue": item.get("newValue"), "newValue": None} for item in added]
        graph_patch = GraphPatch(f"patch-{uuid4().hex}", tuple(patch_ops), f"Undo: {patch.summary}", graph.current_revision_id)
        affected = tuple(diff.get("affected", []))
        return ModificationProposal(f"undo-{uuid4().hex}", len(graph.revisions), affected, f"Undo: {patch.summary}", "undo", tuple(inverse), affected,
            tuple(diff.get("unchanged", [])), tuple(diff.get("regenerated", [])), {"outcome": "pending_graph_verification", "checks": []}, graph_patch)
    attachment = next((item for item in changed if item.get("operation") in {"update_mechanical_attachment", "add_mechanical_attachment"}), None)
    if attachment:
        relation_id, connection_id = attachment["targetId"], attachment["connectionId"]
        if attachment["operation"] == "add_mechanical_attachment":
            if relation_id not in graph.relationships or connection_id not in graph.entities: raise ValueError("nothing_to_undo")
            patch_ops = [GraphOperation(PatchOperation.REMOVE_RELATIONSHIP, target_id=relation_id), GraphOperation(PatchOperation.REMOVE_ENTITY, target_id=connection_id)]
        else:
            old = attachment.get("oldValue") or {}; connection = graph.entities.get(connection_id)
            if relation_id not in graph.relationships or connection is None: raise ValueError("nothing_to_undo")
            metadata = dict(connection.metadata) | {"source_id": old["sourceId"], "target_id": old["targetId"],
                "source_interface": old["sourceInterface"], "target_interface": old["targetInterface"], "connection_type": "mechanical"}
            patch_ops = [GraphOperation(PatchOperation.UPDATE_RELATIONSHIP, target_id=relation_id,
                changes={"source_id": old["sourceId"], "target_id": old["targetId"], "type": "mechanical"}),
                GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=connection_id, changes={"metadata": metadata})]
        inverse = [{**attachment, "oldValue": attachment.get("newValue"), "newValue": attachment.get("oldValue")}]
        graph_patch = GraphPatch(f"patch-{uuid4().hex}", tuple(patch_ops), f"Undo: {patch.summary}", graph.current_revision_id)
        affected = tuple(diff.get("affected", [])); target_id = affected[0] if affected else graph.project_id
        return ModificationProposal(f"undo-{uuid4().hex}", len(graph.revisions), (target_id,), f"Undo: {patch.summary}", "undo", tuple(inverse), affected,
            tuple(diff.get("unchanged", [])), tuple(diff.get("regenerated", [])), {"outcome": "pending_graph_verification", "checks": []}, graph_patch)
    target_id = next((operation.target_id for operation in patch.operations if operation.operation is PatchOperation.UPDATE_ENTITY
                      and operation.target_id in graph.entities and graph.get(operation.target_id).kind is EntityKind.COMPONENT), None)
    if not target_id: raise ValueError("nothing_to_undo")
    target = graph.get(target_id); metadata = dict(target.metadata); inverse = []
    for change in changed:
        path = change["path"].split("."); cursor = metadata
        for key in path[:-1]: cursor = cursor.setdefault(key, {})
        current = cursor.get(path[-1]); cursor[path[-1]] = change["oldValue"]
        inverse.append({**change, "oldValue": current, "newValue": change["oldValue"]})
    graph_patch = GraphPatch(f"patch-{uuid4().hex}", (GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=target_id, changes={"metadata": metadata}),), f"Undo: {patch.summary}", graph.current_revision_id)
    return ModificationProposal(f"undo-{uuid4().hex}", len(graph.revisions), (target_id,), f"Undo: {patch.summary}", "undo", tuple(inverse),
        tuple(diff.get("affected", [target_id])), tuple(diff.get("unchanged", [])), tuple(diff.get("regenerated", [])),
        {"outcome": "accepted_with_warnings", "checks": [{"state": "PASSED", "message": "Prior structured values restored"}]}, graph_patch)


# Strapping pins (0, 2, 5, 12, 15) set the ESP32 boot mode; the picker keeps them out of user-chosen assignments.
from aura.engineering_graph.interfaces import ESP32_STRAPPING_GPIOS, INPUT_FAMILIES, allocate_gpio


def propose_pin_change(graph: EngineeringGraph, base: int, controller_id: str, port: str, gpio: int) -> ModificationProposal:
    """Reassign one controller port to another GPIO; verification still decides conflicts on commit."""
    from aura.engineering_graph.interfaces import ESP32_OUTPUT_GPIOS
    if base != len(graph.revisions): raise ValueError("stale_revision")
    if controller_id not in graph.entities: raise ModificationError("UNKNOWN_CONTROLLER", "That controller is not in the current design.", 404)
    controller = graph.get(controller_id); meta = dict(controller.metadata); params = dict(meta.get("parameters", {}))
    gpio_map = dict(params.get("gpio_map") or {})
    if port not in gpio_map: raise ModificationError("UNKNOWN_PORT", f"{controller.name} has no GPIO-assigned port {port}.", 422)
    if gpio not in ESP32_OUTPUT_GPIOS or gpio in ESP32_STRAPPING_GPIOS:
        raise ModificationError("PIN_NOT_ALLOWED", f"GPIO{gpio} is not an output-capable, non-strapping ESP32 pin.", 422)
    old = gpio_map[port]; gpio_map[port] = gpio; params["gpio_map"] = gpio_map; meta["parameters"] = params
    summary = f"Move {controller.name} {port} from GPIO{old} to GPIO{gpio}"
    patch = GraphPatch(f"patch-{uuid4().hex}", (GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=controller.id, changes={"metadata": meta}),), summary, graph.current_revision_id)
    operations = ({"operation": "replace_parameter", "path": f"parameters.gpio_map.{port}", "oldValue": old, "newValue": gpio},)
    verification = {"outcome": "pending_graph_verification", "checks": [{"state": "PASSED", "message": "Pin is output-capable and not a strapping pin"}]}
    return ModificationProposal(f"proposal-{uuid4().hex}", base, (controller.id,), summary, "pin_change", operations, (controller.id,),
                                ("mechanical assembly",), ("firmware",), verification, patch)


SIGNAL_FAMILIES = frozenset({"temperature_sensor", "environmental_sensor", "distance_sensor", "light_sensor", "motion_sensor", "orientation_sensor",
                             "soil_moisture_sensor", "relay_module", "mosfet_driver", "motor_driver", "servo", "indicator", "switch"})


def propose_add_components(graph: EngineeringGraph, base: int, definition_ids: list[str]) -> ModificationProposal:
    """Add catalogue parts; signal parts get the lowest free safe GPIO. Verification still decides on commit."""
    from aura.verification.catalogue import BY_ID
    if base != len(graph.revisions): raise ValueError("stale_revision")
    if not definition_ids: raise ModificationError("EMPTY_SELECTION", "Select at least one part to add.", 422)
    unknown = [item for item in definition_ids if item not in BY_ID]
    if unknown: raise ModificationError("UNKNOWN_COMPONENT", f"Not in the catalogue: {', '.join(unknown)}.", 404)
    definitions = [BY_ID[item] for item in definition_ids]
    controller = next((e for e in graph.find(kind=EntityKind.COMPONENT) if e.metadata.get("parameters", {}).get("gpio_map") is not None), None)
    if controller is None and any(d.family in SIGNAL_FAMILIES for d in definitions):
        raise ModificationError("NO_CONTROLLER", "These parts need a controller pin, but the design has no controller.", 409)
    params = dict(controller.metadata.get("parameters", {})) if controller else {}
    old_map = dict(params.get("gpio_map") or {}); gpio_map = dict(old_map)
    # Only ports the controller declares can carry a net terminal.
    ports = [i.name for i in component_interfaces(_family(controller), _dimensions(controller), params)
             if i.kind == "control_output" and i.name not in gpio_map] if controller else []
    used = set(gpio_map.values()); picks = []
    for d in definitions:
        pin = allocate_gpio(d.family, d.component_definition_id, used) if d.family in SIGNAL_FAMILIES else None
        if d.family in SIGNAL_FAMILIES and (pin is None or len(picks) >= len(ports)):
            raise ModificationError("NO_FREE_PIN", "Not enough free safe ESP32 pins for these parts.", 409)
        if pin is not None: used.add(pin); picks.append(pin)
    patch_ops, operations, ids = [], [], []
    for definition in definitions:
        suffix = uuid4().hex[:8]; entity_id = f"component-user-{definition.family.replace('_', '-')}-{suffix}"
        size = definition.properties.get("dimensions")
        dims = {key: {"value": value, "unit": "mm"} for key, value in zip(("width", "length", "height"), size.value)} if size else {}
        metadata = {"family": definition.family, "role": definition.family, "component_definition_id": definition.component_definition_id,
                    "interfaces": list(definition.interfaces), "dimensions": dims, "representation_status": "placeholder",
                    "parameters": {"component_definition_id": definition.component_definition_id, "component_definition_version": CATALOGUE_VERSION}}
        if size and size.qualifier != "rated": metadata["dimensions_qualifier"] = size.qualifier
        parent = controller.parent_id if controller else graph.project_id
        patch_ops.append(GraphOperation(PatchOperation.ADD_ENTITY, entity=EngineeringEntity(entity_id, EntityKind.COMPONENT, definition.part_number, parent, metadata)))
        operation = {"operation": "add_component", "targetId": entity_id, "componentDefinitionId": definition.component_definition_id,
                     "path": "components", "oldValue": None, "newValue": definition.part_number, "gpio": None}
        if definition.family in SIGNAL_FAMILIES:
            gpio, port = picks.pop(0), ports.pop(0); gpio_map[port] = gpio
            sensor = definition.family in INPUT_FAMILIES
            source, target = (entity_id, controller.id) if sensor else (controller.id, entity_id)
            kind = "signal" if sensor else "control"
            connection_id = f"connection-user-wire-{suffix}"
            wire = {"source_id": source, "target_id": target, "connection_type": kind,
                    "source_interface": "signal" if sensor else port, "target_interface": port if sensor else "signal"}
            patch_ops += [GraphOperation(PatchOperation.ADD_ENTITY, entity=EngineeringEntity(connection_id, EntityKind.CONNECTION, f"{definition.part_number} signal", graph.project_id, wire)),
                          GraphOperation(PatchOperation.ADD_RELATIONSHIP, relationship=Relationship(f"{connection_id}-edge", source, target, kind, {"connection_id": connection_id}))]
            operation |= {"gpio": gpio, "port": port, "connectionId": connection_id}
        operations.append(operation); ids.append(entity_id)
    affected = tuple(ids)
    if gpio_map != old_map:
        params["gpio_map"] = gpio_map
        patch_ops.append(GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=controller.id, changes={"metadata": dict(controller.metadata) | {"parameters": params}}))
        operations.append({"operation": "replace_parameter", "targetId": controller.id, "path": "parameters.gpio_map", "oldValue": old_map, "newValue": gpio_map})
        affected += (controller.id,)
    summary = f"Add {', '.join(d.part_number for d in definitions)}"
    checks = [{"state": "PASSED", "message": "Parts come from the catalogue; pins avoid strapping and used GPIOs"},
              {"state": "WARNING", "message": "Power and ground are not wired for added parts; they are not electrically complete."}]
    if any(d.family.endswith("_sensor") for d in definitions):
        checks.append({"state": "WARNING", "message": "Single signal pin assigned; bus parts (I2C/SPI) need wiring review."})
    patch = GraphPatch(f"patch-{uuid4().hex}", tuple(patch_ops), summary, graph.current_revision_id)
    return ModificationProposal(f"proposal-{uuid4().hex}", base, affected, summary, "add_component", tuple(operations), affected,
                                ("existing components",), ("firmware",), {"outcome": "pending_graph_verification", "checks": checks}, patch)


# Settings users may change. Ratings, identity and safety claims come from the catalogue and are never editable.
# threshold_c range: DS18B20 datasheet measuring range.
CONFIGURABLE_PARAMETERS = {"threshold_c": (-55.0, 125.0)}


def _decision(action: str, target_id: str, summary: str, **fields: Any) -> ModificationDecision:
    base = {"referenceSemanticId": None, "referenceInterface": None, "targetInterface": None, "scalePercent": None,
            "preserveDimensions": [], "parameterKey": None, "parameterValueJson": None, "componentDefinitionId": None}
    return ModificationDecision(action=action, targetSemanticId=target_id, summary=summary, rationale="Requested from the component card.", **(base | fields))


def propose_parameter_change(graph: EngineeringGraph, base: int, component_id: str, key: str, value: str | int | float | bool) -> ModificationProposal:
    """Deterministic edit of one scalar parameter; verification still decides on commit."""
    if base != len(graph.revisions): raise ValueError("stale_revision")
    if component_id not in graph.entities: raise ModificationError("UNKNOWN_COMPONENT", "That part is not in the current design.", 404)
    target = graph.get(component_id)
    if key not in CONFIGURABLE_PARAMETERS:
        raise ModificationError("PARAMETER_NOT_CONFIGURABLE", f"{key} is a rating, identity or safety fact, not a setting.", 422)
    low, high = CONFIGURABLE_PARAMETERS[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
        raise ModificationError("invalid_parameter_edit", f"{key} must be a number from {low:g} to {high:g}.", 422)
    decision = _decision("SET_PARAMETER", component_id, f"Set {target.name} {key} to {value}"[:240], parameterKey=key, parameterValueJson=json.dumps(value))
    return _set_parameter(graph, base, target, decision, "parameter_change")


def part_interfaces(graph: EngineeringGraph, component_id: str) -> list[dict[str, Any]]:
    if component_id not in graph.entities: raise ModificationError("UNKNOWN_COMPONENT", "That part is not in the current design.", 404)
    entity = graph.get(component_id)
    return [{"name": item.name, "kind": item.kind, "compatible": list(item.compatible)}
            for item in component_interfaces(_family(entity), _dimensions(entity), entity.metadata.get("parameters", {}))]


def propose_connection(graph: EngineeringGraph, base: int, source_id: str, source_interface: str, target_id: str, target_interface: str) -> ModificationProposal:
    """Mount target onto source using the same interface-compatibility rules as attachment edits."""
    if base != len(graph.revisions): raise ValueError("stale_revision")
    for item in (source_id, target_id):
        if item not in graph.entities: raise ModificationError("UNKNOWN_COMPONENT", "That part is not in the current design.", 404)
    target = graph.get(target_id)
    decision = _decision("ATTACH_TO_INTERFACE", target_id, f"Mount {target.name} on {graph.get(source_id).name}"[:240],
                         referenceSemanticId=source_id, referenceInterface=source_interface, targetInterface=target_interface)
    return _attach(graph, base, target, decision, "connection")
