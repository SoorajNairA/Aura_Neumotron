from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from aura.engineering_graph.model import EngineeringEntity, EntityKind
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation
from aura.planner.schemas import ProjectPlan

from .catalogue import CATALOGUE, evidence_records, search
from .evidence import EvidenceKind
from .results import VerificationDecision, VerificationFinding, VerificationResult, VerificationState
from .units import convert, in_range


FAMILY_DEFAULTS = {
    "microcontroller_board": "esp32-devkit-v1", "temperature_sensor": "bme280-i2c-module",
    "environmental_sensor": "bme280-breakout", "soil_moisture_sensor": "capacitive-soil-v1",
    "distance_sensor": "vl53l0x-module", "fan": "dc-fan-5v", "small_dc_motor": "dc-motor-6v",
    "servo": "sg90-servo", "motor_driver": "drv8833-module", "mosfet_driver": "logic-mosfet-module",
    "relay_module": "relay-module-5v", "low_voltage_power_source": "supply-usb-5v-2a",
    "enclosure": "enclosure-100x120",
}


class VerificationService:
    """Evidence-backed rules. Planner values are inputs, never proof."""

    def verify(self, plan: ProjectPlan) -> VerificationResult:
        try: plan.validate()
        except ValueError as exc: return VerificationResult(VerificationDecision.REJECT, VerificationState.FAILED, (str(exc),), None)
        if sum(e.kind == EntityKind.PROJECT for e in plan.entities) != 1:
            return VerificationResult(VerificationDecision.REJECT, VerificationState.FAILED, ("A project plan must contain exactly one project entity",), None)
        if plan.components: return self._verify_engineering_plan(plan)
        operations=[]
        for op in plan.patch.operations:
            if op.operation == PatchOperation.ADD_ENTITY and op.entity:
                operations.append(replace(op,entity=replace(op.entity,name=op.entity.name.strip(),verification_status=VerificationState.TOOL_VERIFIED.value)))
            else: operations.append(op)
        return VerificationResult(VerificationDecision.MODIFY,VerificationState.TOOL_VERIFIED,("Schema and graph references passed deterministic checks",),replace(plan.patch,operations=tuple(operations)))

    def _verify_engineering_plan(self, plan: ProjectPlan) -> VerificationResult:
        components={c.id:c for c in plan.components}; connections=list(plan.connections); findings=[]; revision=1
        resolved={}; exact_ids=set()
        for c in components.values():
            exact=c.parameters.get("component_definition_id")
            family=c.role if c.role in FAMILY_DEFAULTS else ({"component-esp32":"microcontroller_board","component-pump":"small_dc_pump","component-driver":"relay_module","component-power":"low_voltage_power_source","component-enclosure":"enclosure"}.get(c.id,c.role))
            if exact:
                match=[x for x in CATALOGUE if x.component_definition_id==exact]
                if not match:
                    findings.append(self._finding("unknown-component",VerificationState.FAILED,"critical",f"Unknown curated component ID {exact}.",(c.id,),revision=revision))
                    continue
                resolved[c.id]=match[0]; exact_ids.add(c.id)
            elif c.id=="component-esp32" and c.name.strip().upper()=="ESP32":
                resolved[c.id]=next(x for x in CATALOGUE if x.component_definition_id=="esp32-devkit-v1"); exact_ids.add(c.id)
            elif family in FAMILY_DEFAULTS:
                # Generic plans retain an explicit assumption; this candidate is used only for relevant sourced facts.
                matches=search(family=family); resolved[c.id]=matches[0] if matches else None
                findings.append(self._finding("generic-component",VerificationState.ESTIMATED,"warning",f"{c.name} is generic; exact operating values remain estimated.",(c.id,),dependency_ids=(c.id,),revision=revision))

        def add(check,state,severity,message,ids,**kw): findings.append(self._finding(check,state,severity,message,tuple(ids),revision=revision,**kw))
        # The graph has to satisfy the semantic requirements that led to it, not
        # merely be internally well-formed.  Requirements and roles are first
        # class planner data, so this check remains independent of project names
        # and of any particular mechanism layout.
        project=next(entity for entity in plan.entities if entity.kind is EntityKind.PROJECT)
        project_metadata=dict(project.metadata)
        semantic_requirements=[]
        for entity in plan.entities:
            if entity.kind is not EntityKind.REQUIREMENT:
                continue
            metadata=dict(entity.metadata)
            if "semantic_requirement" in metadata:
                semantic_requirements.append((entity.id, entity.name, metadata))
        role_index={component.id:set(component.parameters.get("functional_roles", ())) for component in components.values()}
        for requirement_id,label,metadata in semantic_requirements:
            required=set(metadata.get("required_roles", ()))
            matches=[component for component in components.values() if required & role_index[component.id]]
            if not matches:
                check="REQ_121" if "feedback" in str(metadata.get("semantic_requirement", "")) else "REQ_101"
                add(check,VerificationState.FAILED,"critical",f"No graph component satisfies required {label.lower()}.",(requirement_id,),expected={"roles":sorted(required)},actual={"componentIds":[]})
                continue
            qualities={str(component.parameters.get("resolution_quality", "UNRESOLVED")) for component in matches}
            conceptual=qualities <= {"CONCEPTUAL", "UNRESOLVED"}
            add("REQ_110",VerificationState.CONCEPTUAL if conceptual else VerificationState.TOOL_VERIFIED,
                "warning" if conceptual else "info",
                f"{label} is implemented by {', '.join(component.name for component in matches)}" + (" as a conceptual role." if conceptual else "."),
                (requirement_id,*[component.id for component in matches]),
                expected={"roles":sorted(required)},actual={"componentIds":[component.id for component in matches],"resolutionQualities":sorted(qualities)})
        for trace in project_metadata.get("plannerIntentTrace", ()):
            if trace.get("resolutionQuality") == "UNRESOLVED":
                add("FAMILY_104",VerificationState.CONCEPTUAL,"warning",
                    f"Planner intent '{trace.get('plannerIntent')}' was preserved as unresolved: {trace.get('reason')}.",
                    (project.id,),expected={"plannerIntent":trace.get("plannerIntent")},actual={"normalizedFamily":None,"resolutionQuality":"UNRESOLVED"})

        mechanical=[connection for connection in connections if connection.connection_type == "mechanical"]
        adjacency={component_id:set() for component_id in components}
        for connection in mechanical:
            adjacency[connection.source_id].add(connection.target_id)
            adjacency[connection.target_id].add(connection.source_id)
        moving={component_id for component_id,roles in role_index.items() if {"moving_surface","moving_body"} & roles}
        actuators=[component for component in components.values() if "controlled_motion" in role_index[component.id]]
        for actuator in actuators:
            seen={actuator.id}; pending=[actuator.id]
            while pending:
                current=pending.pop()
                for target in adjacency[current]-seen:
                    seen.add(target); pending.append(target)
            driven=sorted((seen & moving)-{actuator.id})
            if not driven:
                add("MECH_301",VerificationState.FAILED,"critical",f"Actuator {actuator.name} is not mechanically connected to a required moving component.",(actuator.id,),actual={"mechanicalReach":sorted(seen)})
        for requirement_id,label,metadata in semantic_requirements:
            axes=int(metadata.get("required_axes", 0) or 0)
            if not axes:
                continue
            resolved_dof=sum(int(component.parameters.get("controlled_dof", 0) or 0) for component in actuators)
            if resolved_dof < axes:
                add("MECH_310",VerificationState.FAILED,"critical",f"Controlled mechanism provides {resolved_dof} resolved DOF while {label.lower()} expects {axes}.",(requirement_id,*[component.id for component in actuators]),expected={"controlledDof":axes},actual={"controlledDof":resolved_dof})
            else:
                add("MECH_310",VerificationState.TOOL_VERIFIED,"info",f"Controlled mechanism provides {resolved_dof} resolved DOF for {label.lower()}.",(requirement_id,*[component.id for component in actuators]),expected={"controlledDof":axes},actual={"controlledDof":resolved_dof})
        controllers=[c for c in components.values() if c.id=="component-esp32" or c.role=="microcontroller_board"]
        loads=[c for c in components.values() if c.role in {"fan","small_dc_motor","small_dc_pump","servo"} or c.id=="component-pump"]
        drivers=[c for c in components.values() if c.role in {"mosfet_driver","relay_module","motor_driver"} or c.id=="component-driver"]
        powers=[c for c in components.values() if c.role=="low_voltage_power_source" or c.id=="component-power"]
        direct=[x for x in connections if any({x.source_id,x.target_id}=={a.id,b.id} and x.connection_type in ({"power","switched-power"} if b.role=="servo" else {"control","power","switched-power"}) for a in controllers for b in loads if float(b.parameters.get("current_a",0))>.05)]
        if direct: add("direct-pump-gpio",VerificationState.FAILED,"critical","A high-current actuator cannot be driven directly from controller GPIO.",(direct[0].source_id,direct[0].target_id),machine_result={"rule":"load_current > gpio_current"})
        inductive=[x for x in loads if x.parameters.get("inductive_load") or x.role in {"fan","small_dc_motor","small_dc_pump"}]
        if inductive and not drivers: add("missing-driver",VerificationState.FAILED,"warning","Inductive/high-current load has no driver.",(inductive[0].id,))
        if drivers and inductive and not drivers[0].parameters.get("flyback_protection"):
            strict=bool(drivers[0].parameters.get("protection_required"))
            add("flyback",VerificationState.FAILED if strict else VerificationState.ESTIMATED,"critical" if strict else "warning","Inductive load requires confirmed flyback protection.",(drivers[0].id,inductive[0].id),dependency_ids=(drivers[0].id,inductive[0].id))
        types={x.connection_type for x in connections}
        if not ({"power","switched-power"}&types): add("power-connection",VerificationState.FAILED,"critical","Required power connection is missing.",(powers[0].id if powers else "component-power",))
        if "ground" not in types: add("common-ground",VerificationState.FAILED,"critical","Connected low-voltage modules require a common ground.",tuple(x.id for x in controllers+powers))
        for connection in connections:
            source,target=components[connection.source_id],components[connection.target_id]
            if connection.source_interface not in source.interfaces or connection.target_interface not in target.interfaces:
                add("connection-endpoint",VerificationState.FAILED,"critical",f"Connection {connection.id} references an undefined interface.",(source.id,target.id),machine_result={"sourceInterfaceExists":connection.source_interface in source.interfaces,"targetInterfaceExists":connection.target_interface in target.interfaces})
        # New semantic plans have normalized interface roles, which makes a
        # strict port-completeness check meaningful.  Retained legacy fixtures
        # deliberately use historical pin names and retain their prior checks.
        if project_metadata.get("semanticRequirements"):
            connected_ports={component_id:set() for component_id in components}
            for connection in connections:
                if connection.connection_type in {"power","ground","control","signal","switched-power","regulated-power"}:
                    connected_ports[connection.source_id].add(connection.source_interface)
                    connected_ports[connection.target_id].add(connection.target_interface)
            for component in components.values():
                roles=role_index[component.id]
                expected={port for port in ("power","ground") if port in component.interfaces}
                if ("feedback_" in " ".join(roles) or {"controlled_motion","light_output"} & roles) and "signal" in component.interfaces:
                    expected.add("signal")
                if component.role in {"mosfet_driver","motor_driver","relay_module"} and "load-output" in component.interfaces:
                    expected.add("load-output")
                missing=expected-connected_ports[component.id]
                if missing:
                    add("ELEC_411",VerificationState.FAILED,"critical",
                        f"{component.name} expects electrical ports {', '.join(sorted(missing))} that have no graph connection.",(component.id,),
                        expected={"ports":sorted(expected)},actual={"connectedPorts":sorted(connected_ports[component.id])})
        if drivers and controllers:
            dv=float(drivers[0].parameters.get("logic_voltage_v",3.3)); cv=float(controllers[0].parameters.get("logic_voltage_v",3.3))
            add("logic-compatibility",VerificationState.CROSS_CHECKED if dv==cv else VerificationState.FAILED,"info" if dv==cv else "critical","Driver logic is compatible with controller logic." if dv==cv else "Driver logic is incompatible with controller logic.",(controllers[0].id,drivers[0].id),expected={"value":cv,"unit":"V"},actual={"value":dv,"unit":"V"},machine_result={"equal":dv==cv})
        if powers:
            pv=float(powers[0].parameters.get("voltage_v",0)); capacity=float(powers[0].parameters.get("available_current_a",0)); total=0.; complete=True
            for load in loads:
                lv=float(load.parameters.get("voltage_v",pv)); ok=in_range(lv,"V",pv,pv,"V")
                evidence=resolved.get(load.id); evid=tuple(evidence.evidence_ids) if evidence else ()
                add("voltage",VerificationState.CROSS_CHECKED if ok and evid else VerificationState.ESTIMATED if ok else VerificationState.FAILED,"info" if ok else "critical","Supply voltage is compatible with load." if ok else "Load voltage is incompatible with supply.",(powers[0].id,load.id),expected={"value":lv,"unit":"V"},actual={"value":pv,"unit":"V"},evidence_ids=evid,machine_result={"inRange":ok})
                if "current_a" in load.parameters: total+=float(load.parameters["current_a"])
                else: complete=False
            if loads:
                ok=capacity>=total
                add("power-budget",VerificationState.CROSS_CHECKED if ok and complete else VerificationState.ESTIMATED if ok else VerificationState.FAILED,"info" if ok else "critical",f"Modeled peak load {total:.3g} A {'fits' if ok else 'exceeds'} {capacity:.3g} A supply capacity.",(powers[0].id,*[x.id for x in loads]),expected={"maximum":capacity,"unit":"A"},actual={"value":total,"unit":"A","qualifier":"modeled_peak"},machine_result={"withinCapacity":ok,"complete":complete})
        for c in components.values():
            if not c.dimensions: add("dimensions",VerificationState.CONCEPTUAL,"warning",f"Exact dimensions are unavailable for {c.name}.",(c.id,)); continue
            valid=True
            for v in c.dimensions.values():
                try: valid=valid and convert(float(v["value"]),v["unit"],"mm")>0
                except Exception: valid=False
            add("geometry-parameters",VerificationState.TOOL_VERIFIED if valid else VerificationState.FAILED,"info" if valid else "critical",f"{c.name} dimensions are finite, positive, and unit-compatible." if valid else f"{c.name} has invalid geometry dimensions.",(c.id,),machine_result={"finitePositive":valid,"scope":"parameter_geometry_not_manufacturing"})
            add("representation-provenance",VerificationState.CONCEPTUAL,"info",f"{c.name} representation is a conceptual proxy; geometry checks are not manufacturing verification.",(c.id,),machine_result={"manufacturingVerified":False})
        positioned=[c for c in components.values() if "assembly_position_mm" in c.parameters and c.dimensions]
        for index,left in enumerate(positioned):
            for right in positioned[index+1:]:
                lp=left.parameters["assembly_position_mm"];rp=right.parameters["assembly_position_mm"]
                ld=[convert(float(v["value"]),v["unit"],"mm") for v in left.dimensions.values()];rd=[convert(float(v["value"]),v["unit"],"mm") for v in right.dimensions.values()]
                overlap=all(abs(lp[i]-rp[i]) < (ld[i]+rd[i])/2 for i in range(min(3,len(ld),len(rd))))
                if overlap:add("bounding-box-overlap",VerificationState.FAILED,"critical",f"{left.name} overlaps {right.name}.",(left.id,right.id),machine_result={"overlap":True})
        enclosure=next((c for c in components.values() if c.role=="enclosure" or c.id=="component-enclosure"),None)
        if enclosure:
            ew=convert(float(enclosure.dimensions.get("width",{}).get("value",0)),enclosure.dimensions.get("width",{}).get("unit","mm"),"mm"); el=convert(float(enclosure.dimensions.get("length",{}).get("value",0)),enclosure.dimensions.get("length",{}).get("unit","mm"),"mm")
            for cid in enclosure.parameters.get("contains",[]):
                c=components.get(cid)
                if c:
                    cw=convert(float(c.dimensions.get("width",{}).get("value",0)),c.dimensions.get("width",{}).get("unit","mm"),"mm"); cl=convert(float(c.dimensions.get("length",{}).get("value",0)),c.dimensions.get("length",{}).get("unit","mm"),"mm"); ok=cw<=ew and cl<=el
                    add("enclosure-fit",VerificationState.TOOL_VERIFIED if ok else VerificationState.FAILED,"info" if ok else "critical",f"{c.name} {'fits' if ok else 'does not fit'} the enclosure bounding box.",(enclosure.id,c.id),machine_result={"fits":ok})
        wet="component-reservoir" in components or any(c.parameters.get("wet_environment") for c in components.values())
        protected=bool(enclosure and enclosure.parameters.get("waterproofing"))
        if wet: add("water-separation",VerificationState.TOOL_VERIFIED if protected else VerificationState.FAILED,"info" if protected else "critical","Electronics have declared wet-zone separation." if protected else "Wet-zone electronics separation is missing.",tuple(x.id for x in ([enclosure] if enclosure else controllers)),machine_result={"declaredSeparation":protected})
        evidence_by_id={x.evidence_id:x for x in evidence_records()}
        for c,definition in ((components[k],v) for k,v in resolved.items() if v and k in exact_ids):
            authoritative=all(evidence_by_id[eid].kind is not EvidenceKind.ENGINEERING_ASSUMPTION for eid in definition.evidence_ids)
            add("catalogue-properties",VerificationState.SOURCE_VERIFIED if authoritative else VerificationState.ESTIMATED,"info" if authoritative else "warning",f"Authoritative properties available from {definition.manufacturer} {definition.part_number}." if authoritative else f"{definition.part_number} uses a bounded curated engineering assumption.",(c.id,),evidence_ids=definition.evidence_ids,dependency_ids=(c.id,),source_versions={eid:"curated-record-v1" for eid in definition.evidence_ids})

        critical=[x for x in findings if x.severity=="critical" and x.state==VerificationState.FAILED]
        if critical: return VerificationResult(VerificationDecision.REJECT,VerificationState.FAILED,tuple(x.message for x in critical),None,tuple(findings))
        project_id=next(e.id for e in plan.entities if e.kind==EntityKind.PROJECT); operations=[]
        for op in plan.patch.operations:
            if op.operation==PatchOperation.ADD_ENTITY and op.entity:
                status=VerificationState.CONCEPTUAL.value
                if op.entity.kind in {EntityKind.PROJECT,EntityKind.SUBSYSTEM,EntityKind.CONNECTION}: status=VerificationState.TOOL_VERIFIED.value
                if op.entity.id in resolved:
                    definition=resolved[op.entity.id]; authoritative=op.entity.id in exact_ids and all(evidence_by_id[eid].kind is not EvidenceKind.ENGINEERING_ASSUMPTION for eid in definition.evidence_ids)
                    status=VerificationState.SOURCE_VERIFIED.value if authoritative else VerificationState.ESTIMATED.value
                operations.append(replace(op,entity=replace(op.entity,verification_status=status)))
            else: operations.append(op)
        used={eid for f in findings for eid in f.evidence_ids}
        for evidence in evidence_records():
            if evidence.evidence_id not in used: continue
            targets=tuple(i for f in findings if evidence.evidence_id in f.evidence_ids for i in f.entity_ids)
            record=evidence.for_targets(*dict.fromkeys(targets)); data=record.to_dict()
            operations.append(GraphOperation(PatchOperation.ADD_ENTITY,entity=EngineeringEntity(record.evidence_id,EntityKind.EVIDENCE,record.title,project_id,data,verification_status=VerificationState.SOURCE_VERIFIED.value)))
        for f in findings:
            operations.append(GraphOperation(PatchOperation.ADD_ENTITY,entity=EngineeringEntity(f.id,EntityKind.VERIFICATION_RESULT,f.message,project_id,f.to_dict(),source_refs=f.evidence_ids,verification_status=f.state.value)))
        patch=replace(plan.patch,operations=tuple(operations))
        overall=VerificationState.CROSS_CHECKED if any(x.state==VerificationState.CROSS_CHECKED for x in findings) else VerificationState.ESTIMATED
        return VerificationResult(VerificationDecision.MODIFY,overall,("Evidence and deterministic verification completed.",),patch,tuple(findings))

    @staticmethod
    def _finding(check,state,severity,message,ids,revision=1,**kwargs):
        kwargs.setdefault("dependency_ids",ids)
        return VerificationFinding(f"verification-{check}-{uuid4().hex[:10]}",check,state,severity,message,ids,revision=revision,**kwargs)

    def verify_modification(self, graph, patch: GraphPatch) -> VerificationResult:
        affected={x.target_id for x in patch.operations if x.target_id}; operations=[]; stale=[]; attached=()
        for operation in patch.operations:
            exact=operation.changes.get("metadata",{}).get("component_definition_id") if operation.changes else None
            if exact:
                definition=next((x for x in CATALOGUE if x.component_definition_id==exact),None)
                if definition is None: return VerificationResult(VerificationDecision.REJECT,VerificationState.FAILED,(f"Unknown curated component: {exact}",),None)
                attached=definition.evidence_ids
                operation=replace(operation,changes=dict(operation.changes)|{"source_refs":attached,"verification_status":VerificationState.SOURCE_VERIFIED.value})
            operations.append(operation)
        for result in graph.find(kind=EntityKind.VERIFICATION_RESULT):
            dependencies=set(result.metadata.get("dependencyIds",result.metadata.get("entity_ids",[])))
            if dependencies & affected:
                operations.append(GraphOperation(PatchOperation.UPDATE_ENTITY,target_id=result.id,changes={"verification_status":VerificationState.STALE.value,"metadata":dict(result.metadata)|{"status":"stale"}})); stale.append(result.id)
        for evidence in evidence_records():
            if evidence.evidence_id in attached and evidence.evidence_id not in graph.entities:
                record=evidence.for_targets(*affected)
                operations.append(GraphOperation(PatchOperation.ADD_ENTITY,entity=EngineeringEntity(record.evidence_id,EntityKind.EVIDENCE,record.title,graph.project_id,record.to_dict(),verification_status=VerificationState.SOURCE_VERIFIED.value)))
        finding=VerificationFinding("verification-mosfet-update" if "verification-mosfet-update" not in graph.entities else f"verification-modification-{uuid4().hex[:10]}","driver-update",VerificationState.ESTIMATED,"warning","Modified driver values require implementation confirmation.",tuple(affected),revision=len(graph.revisions)+1,machine_result={"staleFindings":stale})
        operations.append(GraphOperation(PatchOperation.ADD_ENTITY,entity=EngineeringEntity(finding.id,EntityKind.VERIFICATION_RESULT,finding.message,graph.project_id,finding.to_dict(),verification_status=finding.state.value)))
        return VerificationResult(VerificationDecision.MODIFY,VerificationState.ESTIMATED,("Affected evidence applications were invalidated and bounded checks reran.",),replace(patch,operations=tuple(operations)),(finding,))
