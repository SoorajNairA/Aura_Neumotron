from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from aura.engineering_graph.model import EngineeringEntity, EntityKind, Relationship
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation
from aura.capabilities import CapabilityStatus, classify_objective
from aura.engineering_graph.interfaces import component_interfaces

from .schemas import (
    ComponentSpec, ConnectionSpec, PlannedEntity, PlannedRelationship, ProjectPlan, ProjectRequest, SubsystemSpec,
    RepresentationRequest, VerificationRequest, WorkspaceEventProposal,
)


@dataclass(frozen=True)
class PlannerRepairAttempt:
    """A single, graph-aware replan.  The candidate itself is never committed."""
    plan: ProjectPlan
    context: dict[str, Any]
    metadata: dict[str, Any]


class PlannerService:
    """Produce a deterministic, structured proposal without executing it."""

    def plan(self, request: ProjectRequest) -> ProjectPlan:
        request.validate()
        capability=classify_objective(request.objective)
        if capability["status"] in {CapabilityStatus.UNSUPPORTED.value,CapabilityStatus.NEEDS_CLARIFICATION.value}:
            raise ValueError(capability)
        # Normal production always compiles semantic intent.  It never selects a
        # complete project graph by matching a demo or benchmark phrase.
        return self._semantic_plan(request, capability["status"])
        project_id = self._id(request.project_name, "project")
        assembly_id = self._id(request.project_name, "assembly")
        planned = [
            PlannedEntity(project_id, EntityKind.PROJECT, request.project_name.strip()),
            PlannedEntity(assembly_id, EntityKind.ASSEMBLY, "Primary Assembly", project_id),
        ]
        for index, requirement in enumerate(request.requirements, 1):
            planned.append(PlannedEntity(
                self._id(request.project_name, f"requirement-{index}"), EntityKind.REQUIREMENT,
                requirement.strip(), project_id,
            ))
        for index, assumption in enumerate(request.assumptions, 1):
            planned.append(PlannedEntity(
                self._id(request.project_name, f"assumption-{index}"), EntityKind.ASSUMPTION,
                assumption.strip(), project_id,
            ))
        for index, component in enumerate(request.components, 1):
            planned.append(PlannedEntity(
                self._id(request.project_name, f"component-{index}"), EntityKind.COMPONENT,
                component.strip(), assembly_id,
            ))
        representation_id = self._id(request.project_name, "representation")
        planned.append(PlannedEntity(
            representation_id, EntityKind.REPRESENTATION, request.representation,
            project_id, (("representation_type", request.representation),),
        ))

        relationships = tuple(
            PlannedRelationship(
                self._id(request.project_name, f"contains-{index}"), assembly_id, entity.id, "contains"
            )
            for index, entity in enumerate(planned)
            if entity.kind == EntityKind.COMPONENT
        )
        operations = [
            GraphOperation(PatchOperation.ADD_ENTITY, entity=EngineeringEntity(
                id=item.id, kind=item.kind, name=item.name, parent_id=item.parent_id,
                metadata=dict(item.metadata),
            ))
            for item in planned
        ]
        operations.extend(
            GraphOperation(PatchOperation.ADD_RELATIONSHIP, relationship=Relationship(
                id=item.id, source_id=item.source_id, target_id=item.target_id, type=item.type,
            ))
            for item in relationships
        )
        patch = GraphPatch(
            id=self._id(request.project_name, "initial-patch"), operations=tuple(operations),
            summary=f"Create engineering graph for {request.project_name.strip()}",
        )
        plan = ProjectPlan(
            request=request, entities=tuple(planned), relationships=relationships, patch=patch,
            representation_requests=(RepresentationRequest(project_id, request.representation),),
            verification_request=VerificationRequest(patch.id, ("schema", "references", "safety")),
            workspace_events=(WorkspaceEventProposal("project.created", project_id),),
        )
        plan.validate()
        return plan

    def _semantic_plan(self,request:ProjectRequest,capability_status:str)->ProjectPlan:
        """Compile intent into families without replacing an unknown role with a look-alike.

        This is deliberately a small vocabulary of *roles*, not a menu of project
        templates.  A useful unknown is kept as a conceptual component, with the
        original Planner intent and resolution class carried into the graph.
        """
        text=request.objective.lower();planner_labels=" ".join(request.components).lower();project_id=self._id(request.objective,"project")
        semantic_requirements=[]
        def require(key,label,roles,*,axes=0):
            if not any(item["key"]==key for item in semantic_requirements):
                semantic_requirements.append({"key":key,"label":label,"roles":list(roles),"axes":axes,"critical":True})
        require("controller","Control logic",("controller",))
        require("power","Low-voltage power",("power",))
        motion_words=("move","rotate","turn","lift","tilt","pan","balance","conveyor","dispens","arm","drive")
        # "Drawer opened" is a sensed state, not necessarily an instruction to
        # actuate the drawer.  Open/close only imply motion for a moving closure.
        non_indicator_motion=("turn" in text and "turn on" not in text and "turns on" not in text)
        needs_motion=any(word in text for word in motion_words if word != "turn") or non_indicator_motion or any(word in planner_labels for word in ("motor","servo","actuator")) or (any(word in text for word in ("lid","flap","shade")) and any(word in text for word in ("open","close")))
        mobile_drive=any(re.search(rf"\b{re.escape(word)}\b", text) or re.search(rf"\b{re.escape(word)}\b", planner_labels) for word in ("wheel","drive","vehicle","car","chassis"))
        if any(word in text for word in ("plate","platform","surface","conveyor")): require("moving-surface","Moving surface or platform",("moving_surface",))
        if any(word in text for word in ("ball","object","drawer","lid","camera")): require("moving-body","Required moving body",("moving_body",))
        if any(word in text for word in ("support","plate","platform","conveyor","lid","drawer","camera")): require("support","Stationary support",("support",))
        if needs_motion: require("controlled-motion","Controlled actuation",("controlled_motion",))
        if mobile_drive:
            require("drive-output","Driven moving component",("drive_output",))
            require("support","Stationary support",("support",))
        if any(re.search(rf"\b{re.escape(word)}\b", text) or re.search(rf"\b{re.escape(word)}\b", planner_labels) for word in ("remote","wireless","receiver","bluetooth")):
            require("remote-control-input","Remote control input",("remote_control_input",))
        multi_axis=2 if "two-axis" in text or ("pan" in text and "tilt" in text) or "balanc" in text else 0
        if multi_axis: require("controlled-axes",f"{multi_axis}-axis controlled motion",("controlled_motion",),axes=multi_axis)
        if any(word in text for word in ("position","balanc","track")): require("position-feedback","Position/state feedback",("feedback_position",))
        if "temperature" in text or "thermal" in text or "warm" in text: require("temperature-feedback","Temperature feedback",("feedback_temperature",))
        if "drawer" in text and any(word in text for word in ("detect","opened","open state")): require("open-state-feedback","Open-state feedback",("feedback_open_state",))
        if "light" in text and any(word in text for word in ("turn on","turns on","output","illuminate")): require("light-output","Light output",("light_output",))

        families={"controller":1,"power":1,"enclosure":1}
        def include(family:str,count:int=1)->None: families[family]=max(families.get(family,0),count)
        # Reusable objective-to-role rules.  None selects a complete named project.
        if any(word in text for word in ("warm","temperature","thermal")): include("temperature-sensor")
        if any(word in text for word in ("bright","illumination")): include("light-sensor")
        if any(word in text for word in ("humidity","pressure","weather","environment")): include("environmental-sensor")
        if any(word in text for word in ("distance","range")): include("distance-sensor")
        if any(word in text for word in ("airflow","fan","ventilation")): include("fan");include("driver")
        if any(word in text for word in ("water","liquid","soil","pump","fluid","irrigation")): include("container");include("tube");include("pump");include("driver")
        if any(word in text for word in ("dispense","dispensing","food","portion")): include("container");include("servo");include("dispensing-mechanism");include("mounting-plate")
        if any(word in text for word in ("lid","flap","shade")): include("lid");include("hinge");include("servo");include("mounting-plate")
        if "drawer" in text: include("drawer");include("open-state-sensor")
        if "light" in text and any(word in text for word in ("turn on","turns on","output","illuminate")): include("indicator")
        if "conveyor" in text or "belt" in text: include("conveyor");include("motor");include("driver");include("support")
        if mobile_drive: include("chassis");include("drive-wheel",2);include("motor");include("motor-driver")
        if any(re.search(rf"\b{re.escape(word)}\b", text) or re.search(rf"\b{re.escape(word)}\b", planner_labels) for word in ("remote","wireless","receiver","bluetooth")): include("wireless-control")
        if "camera" in text: include("camera-platform");include("support")
        if any(word in text for word in ("plate","platform")): include("controlled-platform");include("support")
        if "ball" in text or "object" in text: include("tracked-object")
        if any(word in text for word in ("position","balanc","track")): include("position-sensor")
        if needs_motion and not any(family in families for family in ("servo","motor")): include("servo")
        if needs_motion: include("mechanism");include("mounting-plate")
        if multi_axis: include("servo",multi_axis);include("mechanism",multi_axis);include("mounting-plate")

        specs={
          "controller":("Controller board","microcontroller_board","electronics",{"logic_voltage_v":3.3,"gpio_max_current_ma":12,"functional_roles":["controller"],"resolution_quality":"EXACT"},(52,28,8)),
          "power":("Low-voltage power source","low_voltage_power_source","power",{"voltage_v":5.0,"available_current_a":3.0,"mains_exposed":False,"functional_roles":["power"],"resolution_quality":"EXACT"},(48,30,18)),
          "enclosure":("Protective enclosure","enclosure","structure",{"contains":["component-controller"],"waterproofing":"splash-resistant" if "tank" in text else "basic","functional_roles":["support"],"resolution_quality":"COMPATIBLE_GENERIC"},(120,90,55)),
          "temperature-sensor":("Temperature sensor","temperature_sensor","sensor",{"supply_voltage_v":3.3,"signal_voltage_v":3.3,"threshold_c":26,"functional_roles":["feedback_temperature"],"measures":["temperature"],"resolution_quality":"EXACT"},(22,16,6)),
          "light-sensor":("Ambient light sensor","light_sensor","sensor",{"supply_voltage_v":3.3,"signal_voltage_v":3.3,"functional_roles":["feedback_light"],"measures":["light"],"resolution_quality":"COMPATIBLE_GENERIC"},(22,16,6)),
          "environmental-sensor":("Environmental sensor","environmental_sensor","sensor",{"supply_voltage_v":3.3,"measurements":["temperature","humidity","pressure"],"functional_roles":["feedback_environment"],"resolution_quality":"EXACT"},(24,18,6)),
          "distance-sensor":("Generic distance sensor","distance_sensor","sensor",{"supply_voltage_v":5.0,"functional_roles":["feedback_distance"],"measures":["distance"],"resolution_quality":"COMPATIBLE_GENERIC"},(45,22,18)),
          "position-sensor":("Conceptual position sensor","conceptual_sensor","sensor",{"supply_voltage_v":5.0,"signal_voltage_v":3.3,"functional_roles":["feedback_position"],"measures":["position"],"resolution_quality":"CONCEPTUAL","research_required":True},(35,24,12)),
          "open-state-sensor":("Conceptual open-state sensor","conceptual_sensor","sensor",{"supply_voltage_v":5.0,"signal_voltage_v":3.3,"functional_roles":["feedback_open_state"],"measures":["open_state"],"resolution_quality":"CONCEPTUAL"},(24,18,8)),
          "driver":("Logic-level MOSFET driver","mosfet_driver","electronics",{"logic_voltage_v":3.3,"load_voltage_v":5.0,"max_current_a":3.0,"flyback_protection":True,"functional_roles":["actuator_driver"],"resolution_quality":"EXACT"},(32,24,8)),
          "motor-driver":("Generic motor driver","motor_driver","electronics",{"logic_voltage_v":3.3,"load_voltage_v":5.0,"max_current_a":1.2,"flyback_protection":True,"functional_roles":["actuator_driver"],"resolution_quality":"COMPATIBLE_GENERIC"},(32,24,8)),
          "fan":("Desk fan","fan","actuator",{"voltage_v":5.0,"current_a":0.5,"inductive_load":True,"functional_roles":["airflow_output"],"resolution_quality":"EXACT"},(90,30,90)),
          "servo":("Small servo","servo","actuator",{"voltage_v":5.0,"current_a":0.8,"inductive_load":False,"functional_roles":["controlled_motion"],"controlled_dof":1,"resolution_quality":"EXACT"},(40,20,38)),
          "motor":("Small DC motor","small_dc_motor","actuator",{"voltage_v":5.0,"current_a":0.6,"inductive_load":True,"functional_roles":["controlled_motion","conveyor_drive"],"controlled_dof":1,"resolution_quality":"COMPATIBLE_GENERIC"},(30,45,30)),
          "chassis":("Structural chassis","mounting_plate","structure",{"functional_roles":["support"],"resolution_quality":"CONCEPTUAL"},(180,110,18)),
          "drive-wheel":("Drive wheel","drive_wheel","mechanical",{"functional_roles":["moving_body","drive_output"],"resolution_quality":"CONCEPTUAL"},(52,52,18)),
          "wireless-control":("Conceptual wireless control module","wireless_module","electronics",{"functional_roles":["remote_control_input"],"resolution_quality":"CONCEPTUAL"},(32,20,8)),
          "container":("Container","container","mechanical",{"capacity_l":1.5,"wet_environment":any(word in text for word in ("water","liquid","soil","pump")),"functional_roles":["moving_body"],"resolution_quality":"COMPATIBLE_GENERIC"},(110,100,150)),
          "dispensing-mechanism":("Conceptual dispensing wheel","generic_mechanical_part","mechanical",{"functional_roles":["moving_surface"],"resolution_quality":"CONCEPTUAL"},(55,55,25)),
          "indicator":("Low-voltage light output","indicator","electronics",{"voltage_v":5.0,"functional_roles":["light_output"],"resolution_quality":"COMPATIBLE_GENERIC"},(18,12,8)),
          "lid":("Lightweight lid","lid","mechanical",{"mass_g":120,"functional_roles":["moving_body","moving_surface"],"resolution_quality":"COMPATIBLE_GENERIC"},(120,90,6)),
          "drawer":("Drawer body","generic_mechanical_part","mechanical",{"functional_roles":["moving_body"],"resolution_quality":"CONCEPTUAL"},(160,100,45)),
          "hinge":("Hinge","hinge","mechanical",{"functional_roles":["support"],"resolution_quality":"COMPATIBLE_GENERIC"},(80,10,10)),
          "mounting-plate":("Mounting plate","mounting_plate","structure",{"functional_roles":["support"],"resolution_quality":"COMPATIBLE_GENERIC"},(150,100,6)),
          "support":("Structural support","mounting_plate","structure",{"functional_roles":["support"],"resolution_quality":"CONCEPTUAL"},(150,100,12)),
          "mechanism":("Driven mechanism","generic_mechanical_part","mechanical",{"functional_roles":["moving_surface"],"resolution_quality":"CONCEPTUAL"},(100,60,8)),
          "controlled-platform":("Controlled platform","generic_mechanical_part","mechanical",{"functional_roles":["moving_surface","moving_body"],"resolution_quality":"CONCEPTUAL"},(140,100,8)),
          "camera-platform":("Camera platform","generic_mechanical_part","mechanical",{"functional_roles":["moving_surface","moving_body"],"resolution_quality":"CONCEPTUAL"},(80,60,18)),
          "conveyor":("Conveyor surface","generic_mechanical_part","mechanical",{"functional_roles":["moving_surface","moving_body"],"resolution_quality":"CONCEPTUAL"},(180,70,20)),
          "tracked-object":("Tracked object","tracked_object","mechanical",{"functional_roles":["moving_body"],"resolution_quality":"CONCEPTUAL"},(24,24,24)),
          "tube":("Fluid tube","tube","mechanical",{"resolution_quality":"CONCEPTUAL"},(10,150,10)),
          "pump":("Low-voltage pump","small_dc_pump","actuator",{"voltage_v":5.0,"current_a":0.8,"inductive_load":True,"functional_roles":["fluid_drive"],"resolution_quality":"COMPATIBLE_GENERIC"},(40,60,40)),
        }
        curated={"controller":"esp32-devkit-v1","temperature-sensor":"bme280-i2c-module","environmental-sensor":"bme280-breakout","distance-sensor":"vl53l0x-module","fan":"dc-fan-5v","servo":"sg90-servo","driver":"logic-mosfet-module","motor-driver":"drv8833-module","power":"supply-usb-5v-2a"}
        raw_trace=[];raw_counts={}
        for raw in request.components:
            resolved=self._resolve_component_intent(raw,text)
            raw_trace.append({"plannerIntent":raw,**resolved})
            family=resolved.get("normalizedFamily")
            if family: raw_counts[family]=raw_counts.get(family,0)+1
        for family,count in raw_counts.items(): include(family,count)
        order=list(families);roles=tuple(dict.fromkeys(specs[family][2] for family in order));subsystems=tuple(SubsystemSpec(f"subsystem-{role}",role.title(),role,"Deterministic semantic subsystem.") for role in roles)
        components=[];component_by_family={}
        for family in order:
            name,kind,role,base_params,dims=specs[family];count=families[family]
            matching=[item for item in raw_trace if item.get("normalizedFamily")==family]
            for index in range(count):
                suffix="" if count==1 else f"-{index+1}";cid=f"component-{family}{suffix}";params=dict(base_params)
                if family in curated: params["component_definition_id"]=curated[family]
                if index<len(matching):
                    params["planner_intent"]=matching[index]["plannerIntent"];params["resolution_quality"]=matching[index]["resolutionQuality"];params["resolution_reason"]=matching[index]["reason"]
                    if matching[index]["resolutionQuality"] != "EXACT": params.pop("component_definition_id",None)
                else: params["planner_intent"]=name
                physical=component_interfaces(kind,tuple(float(value) for value in dims));interface_names=tuple(dict.fromkeys(item.name for item in physical))
                components.append(ComponentSpec(cid,name,kind,f"subsystem-{role}",f"{name} for the requested low-voltage system.",params,interface_names,{key:{"value":value,"unit":"mm"} for key,value in zip(("width","length","height"),dims)},assumption_refs=(f"assumption-{family}",)))
                component_by_family.setdefault(family,[]).append(cid)
        ids={c.id for c in components};connections=[];by_component={c.id:c for c in components};controller_signal=0
        def connect(a,b,kind):
            nonlocal controller_signal
            endpoint={"power":("power","power"),"ground":("ground","ground"),"control":("signal","signal"),"signal":("signal","signal"),"switched-power":("signal","power"),"regulated-power":("power","power")}.get(kind)
            if kind in {"control","signal"}:
                if a in by_component and by_component[a].role in {"microcontroller_board","controller"}:
                    controller_signal+=1;endpoint=(f"signal-{min(controller_signal,8)}","signal")
                elif b in by_component and by_component[b].role in {"microcontroller_board","controller"}:
                    controller_signal+=1;endpoint=("signal",f"signal-{min(controller_signal,8)}")
            # A downstream actuator body is fixed to the prior link.  Its
            # rotating output is reserved for the next driven link, so it is
            # never mated through the prior link's rotating input.
            if kind=="mechanical" and a in by_component and b in by_component and by_component[a].role=="generic_mechanical_part" and by_component[b].role=="servo":
                endpoint=("end-face","body-mount")
            if kind=="switched-power" and a in by_component and by_component[a].role in {"mosfet_driver","motor_driver","relay_module"}:
                endpoint=("load-output","power")
            if endpoint is None and a in by_component and b in by_component:
                left=component_interfaces(by_component[a].role,tuple(float(x.get("value",1)) for x in by_component[a].dimensions.values()));right=component_interfaces(by_component[b].role,tuple(float(x.get("value",1)) for x in by_component[b].dimensions.values()))
                endpoint=next(((x.name,y.name) for x in left for y in right if y.kind in x.compatible),("mechanical","mechanical"))
            if a in ids and b in ids and endpoint: connections.append(ConnectionSpec(f"connection-{a[10:]}-{b[10:]}-{kind}",a,b,endpoint[0],endpoint[1],kind,f"{kind.title()} connection."))
        controller=component_by_family["controller"][0];power=component_by_family["power"][0]
        sensors=[c.id for c in components if any(str(role).startswith("feedback_") for role in c.parameters.get("functional_roles",[]))]
        for sensor in sensors: connect(sensor,controller,"signal")
        for remote in component_by_family.get("wireless-control",[]): connect(remote,controller,"signal")
        drivers=component_by_family.get("driver",[])+component_by_family.get("motor-driver",[]);actuators=[c.id for c in components if "controlled_motion" in c.parameters.get("functional_roles",[]) or c.role in {"fan","small_dc_pump"}]
        for actuator in actuators: connect(drivers[0] if drivers and by_component[actuator].role!="servo" else controller,actuator,"switched-power" if drivers and by_component[actuator].role!="servo" else "control")
        for indicator in component_by_family.get("indicator",[]): connect(controller,indicator,"control")
        if drivers: connect(controller,drivers[0],"control")
        driver_controlled={actuator for actuator in actuators if drivers and by_component[actuator].role!="servo"}
        for target in sorted(item.id for item in components if item.id!=power and {"power","ground"}.issubset(item.interfaces)):
            if target not in driver_controlled: connect(power,target,"power")
            connect(power,target,"ground")
        servos=component_by_family.get("servo",[]);mechanisms=component_by_family.get("mechanism",[]);platforms=component_by_family.get("controlled-platform",[])+component_by_family.get("camera-platform",[])+component_by_family.get("conveyor",[])+component_by_family.get("lid",[])+component_by_family.get("dispensing-mechanism",[])
        mounts=component_by_family.get("mounting-plate",[])+component_by_family.get("support",[])
        if servos and mounts: connect(mounts[0],servos[0],"mechanical")
        if len(servos)>1 and mechanisms:
            for index,servo in enumerate(servos):
                stage=mechanisms[min(index,len(mechanisms)-1)];connect(servo,stage,"mechanical")
                if index+1<len(servos): connect(stage,servos[index+1],"mechanical")
            if platforms: connect(mechanisms[min(len(servos)-1,len(mechanisms)-1)],platforms[0],"mechanical")
        elif servos and platforms: connect(servos[0],platforms[0],"mechanical")
        elif servos and mechanisms: connect(servos[0],mechanisms[0],"mechanical")
        if component_by_family.get("hinge",[]) and component_by_family.get("lid",[]): connect(component_by_family["hinge"][0],component_by_family["lid"][0],"mechanical")
        if component_by_family.get("motor",[]) and component_by_family.get("conveyor",[]): connect(component_by_family["motor"][0],component_by_family["conveyor"][0],"mechanical")
        motors=component_by_family.get("motor",[]);wheels=component_by_family.get("drive-wheel",[]);chassis=component_by_family.get("chassis",[])
        if motors and chassis:
            for index,motor in enumerate(motors): connect(chassis[min(index,len(chassis)-1)],motor,"mechanical")
        if motors and wheels:
            for index,motor in enumerate(motors): connect(motor,wheels[min(index,len(wheels)-1)],"mechanical")
        entities=[PlannedEntity(project_id,EntityKind.PROJECT,request.project_name,metadata=(("objective",request.objective),("capability_status",capability_status),("plannerIntentTrace",raw_trace),("semanticRequirements",semantic_requirements)))]
        entities += [PlannedEntity(s.id,EntityKind.SUBSYSTEM,s.name,project_id,(("role",s.role),)) for s in subsystems]
        entities += [PlannedEntity(f"requirement-{item['key']}",EntityKind.REQUIREMENT,item["label"],project_id,tuple({"semantic_requirement":item["key"],"required_roles":item["roles"],"required_axes":item["axes"],"critical":item["critical"]}.items())) for item in semantic_requirements]
        entities += [PlannedEntity(f"requirement-declared-{i}",EntityKind.REQUIREMENT,value,project_id,(("declared_requirement",True),)) for i,value in enumerate(request.requirements,1)]
        entities += [PlannedEntity(c.id,EntityKind.COMPONENT,c.name,c.subsystem_id,tuple({"role":c.role,"family":c.role,"parameters":c.parameters,"interfaces":list(c.interfaces),"dimensions":c.dimensions,"representation_status":"placeholder","assumption_refs":list(c.assumption_refs)}.items())) for c in components]
        entities += [PlannedEntity(f"assumption-{i}",EntityKind.ASSUMPTION,value,project_id) for i,value in enumerate(("Use 5 V isolated low-voltage power","Exact mechanical fit remains conceptual"),1)]
        entities += [PlannedEntity(c.id,EntityKind.CONNECTION,c.description,project_id,tuple({"source_id":c.source_id,"target_id":c.target_id,"source_interface":c.source_interface,"target_interface":c.target_interface,"connection_type":c.connection_type}.items())) for c in connections]
        operations=[GraphOperation(PatchOperation.ADD_ENTITY,entity=EngineeringEntity(e.id,e.kind,e.name,e.parent_id,dict(e.metadata))) for e in entities];relationships=tuple(PlannedRelationship(c.id+"-edge",c.source_id,c.target_id,c.connection_type) for c in connections)
        operations += [GraphOperation(PatchOperation.ADD_RELATIONSHIP,relationship=Relationship(r.id,r.source_id,r.target_id,r.type,{"connection_id":r.id.removesuffix("-edge")})) for r in relationships]
        patch=GraphPatch(self._id(request.objective,"initial-patch"),tuple(operations),f"Create {request.project_name}")
        plan=ProjectPlan(request,tuple(entities),relationships,patch,(RepresentationRequest(project_id,"system_diagram"),),VerificationRequest(patch.id,("structure","electrical","physical","safety","objective_coverage")),(WorkspaceEventProposal("project.started",project_id),),subsystems,tuple(components),tuple(connections),("Use low-voltage DC only","Unsupported certification remains explicit"))
        plan.validate();return plan

    def repair_context(self, plan: ProjectPlan, verification: Any) -> tuple[dict[str, Any], list[str]]:
        """Extract the bounded, provider-neutral context for one graph repair."""
        critical=[finding for finding in verification.findings if finding.severity=="critical" and finding.state.value=="failed"]
        component_by_id={component.id:component for component in plan.components}
        implicated={entity_id for finding in critical for entity_id in finding.entity_ids if entity_id in component_by_id}
        relevant=[]
        for component_id in sorted(implicated):
            component=component_by_id[component_id]
            dimensions=tuple(float(value.get("value",1)) for value in component.dimensions.values())
            relevant.append({"id":component.id,"family":component.role,"interfaces":[{"name":item.name,"type":item.kind,"compatible":list(item.compatible)} for item in component_interfaces(component.role,dimensions)]})
        checks={finding.check for finding in critical}
        additions=[]
        roles={role for component in plan.components for role in component.parameters.get("functional_roles",())}
        has_motor=any(component.role=="small_dc_motor" for component in plan.components)
        has_servo=any(component.role=="servo" for component in plan.components)
        has_inductive=any(component.role in {"small_dc_motor","small_dc_pump","fan"} for component in plan.components)
        has_driver=any(component.role in {"mosfet_driver","motor_driver","relay_module"} for component in plan.components)
        if has_inductive and not has_driver and ({"direct-pump-gpio","missing-driver","ELEC_411","connection-endpoint"}&checks): additions.append("compatible motor driver")
        if has_motor and ({"MECH_301","connection-endpoint"}&checks): additions.extend(("structural chassis","drive wheel"))
        if has_servo and ({"MECH_301","connection-endpoint"}&checks): additions.extend(("structural support","driven mechanism"))
        if {"power-connection","common-ground","ELEC_411"}&checks: additions.append("low-voltage power supply")
        if "remote_control_input" in roles: additions.append("wireless control module")
        additions=list(dict.fromkeys(additions))
        context={
            "originalObjective":plan.request.objective,
            "normalizedGraph":{"components":[{"id":component.id,"family":component.role,"interfaces":list(component.interfaces),"roles":component.parameters.get("functional_roles",[])} for component in plan.components],"connections":[{"id":connection.id,"type":connection.connection_type,"source":connection.source_id,"sourceInterface":connection.source_interface,"target":connection.target_id,"targetInterface":connection.target_interface} for connection in plan.connections]},
            "criticalFindings":[{"code":finding.check,"message":finding.message,"entityIds":list(finding.entity_ids),"expected":finding.expected,"actual":finding.actual} for finding in critical],
            "relevantComponentInterfaces":relevant,
            "repairRules":["Use only declared compatible interfaces.","Place a driver between controller GPIO and a high-current inductive actuator.","Attach actuator bodies to support and rotating outputs to driven components.","Recompile and reverify exactly once."],
        }
        return context, additions

    def repair(self, plan: ProjectPlan, verification: Any) -> PlannerRepairAttempt:
        """Perform one deterministic, interface-aware replan after graph rejection.

        This deliberately recompiles a new candidate through ``plan`` rather
        than mutating an invalid graph.  It uses only families implicated by
        the rejected connections/findings, so it is bounded and auditable.
        """
        context, additions=self.repair_context(plan,verification)
        repaired_request=ProjectRequest(plan.request.project_name,plan.request.objective,plan.request.requirements,
            components=tuple(dict.fromkeys((*plan.request.components,*additions))),assumptions=tuple(dict.fromkeys((*plan.request.assumptions,"One bounded semantic repair was applied"))),representation=plan.request.representation)
        repaired=self.plan(repaired_request)
        return PlannerRepairAttempt(repaired,context,{"repairAttempted":True,"repairProvider":"deterministic_semantic_repair","repairAdditions":additions,"criticalFindingCountBefore":len(context["criticalFindings"])})

    @staticmethod
    def _resolve_component_intent(intent:str,objective:str)->dict[str,str|None]:
        """Resolve a Planner label only when its functional language is retained."""
        label=intent.lower().strip()
        if ("tank" in label or "level" in label) and any(word in objective for word in ("position","balanc","track")) and not any(word in objective for word in ("tank","level")):
            return {"normalizedFamily":None,"resolutionQuality":"UNRESOLVED","reason":"level sensing does not preserve the objective's position-feedback intent"}
        rules=(
            (("arduino","nano"),"controller","COMPATIBLE_GENERIC"),(("controller","esp32","microcontroller"),"controller","EXACT"),(("power","battery","supply"),"power","EXACT"),
            (("servo",),"servo","EXACT"),(("temperature",),"temperature-sensor","EXACT"),(("ambient light","light sensor"),"light-sensor","COMPATIBLE_GENERIC"),
            (("humidity","pressure","environmental"),"environmental-sensor","EXACT"),(("distance","range","level sensor"),"distance-sensor","COMPATIBLE_GENERIC"),
            (("position","tracking","camera-based"),"position-sensor","CONCEPTUAL"),(("drawer","open-state","reed"),"open-state-sensor","CONCEPTUAL"),
            (("conveyor","belt"),"conveyor","CONCEPTUAL"),(("motor driver","h-bridge"),"motor-driver","COMPATIBLE_GENERIC"),(("motor",),"motor","COMPATIBLE_GENERIC"),(("fan",),"fan","EXACT"),(("pump",),"pump","COMPATIBLE_GENERIC"),
            (("driver","mosfet","relay"),"driver","EXACT"),(("wheel",),"drive-wheel","CONCEPTUAL"),(("chassis",),"chassis","CONCEPTUAL"),(("remote","wireless","receiver","bluetooth"),"wireless-control","CONCEPTUAL"),(("container","reservoir"),"container","COMPATIBLE_GENERIC"),(("tube","tubing"),"tube","COMPATIBLE_GENERIC"),
            (("lid",),"lid","COMPATIBLE_GENERIC"),(("hinge",),"hinge","COMPATIBLE_GENERIC"),(("plate","platform"),"controlled-platform","CONCEPTUAL"),
            (("ball","object"),"tracked-object","CONCEPTUAL"),(("camera",),"camera-platform","CONCEPTUAL"),(("arm","link","mechanism"),"mechanism","CONCEPTUAL"),
        )
        for terms,family,quality in rules:
            if any(term in label for term in terms): return {"normalizedFamily":family,"resolutionQuality":quality,"reason":"functional terms match the retained family semantics"}
        return {"normalizedFamily":None,"resolutionQuality":"UNRESOLVED","reason":"no safe family preserves this Planner intent"}

    def irrigation_benchmark_plan(self, request: ProjectRequest) -> ProjectPlan:
        """Legacy fixture retained only for test/demo reset tooling, never `plan`."""
        project_id = "project-auto-irrigation-v1"
        subsystems = (
            SubsystemSpec("subsystem-controller", "Controller subsystem", "sense and control", "Reads moisture and controls water delivery."),
            SubsystemSpec("subsystem-water", "Water subsystem", "store and move water", "Routes water from reservoir to plant."),
            SubsystemSpec("subsystem-power", "Power subsystem", "low-voltage supply", "Supplies regulated low-voltage power."),
            SubsystemSpec("subsystem-structure", "Physical structure", "protect electronics", "Separates electronics from water."),
        )
        components = (
            ComponentSpec("component-esp32", "ESP32", "controller", "subsystem-controller", "Microcontroller that reads the sensor and commands the driver.", {"logic_voltage_v": 3.3, "gpio_max_current_ma": 12}, ("3v3", "gnd", "gpio-sensor", "gpio-pump"), {"width": {"value": 28, "unit": "mm"}, "length": {"value": 52, "unit": "mm"}}, evidence_refs=("evidence-esp32-datasheet",)),
            ComponentSpec("component-sensor", "Soil-moisture sensor", "soil sensing", "subsystem-controller", "Low-voltage sensor used to estimate soil moisture.", {"supply_voltage_v": 3.3, "signal_voltage_v": 3.3}, ("vcc", "gnd", "signal"), {"width": {"value": 20, "unit": "mm"}, "length": {"value": 60, "unit": "mm"}}, assumption_refs=("assumption-capacitive-sensor",)),
            ComponentSpec("component-driver", "Relay driver", "pump switching", "subsystem-controller", "Separates the ESP32 GPIO from the pump load.", {"logic_voltage_v": 3.3, "load_voltage_v": 5.0, "max_current_a": 2.0, "driver_type": "relay", "flyback_protection": False}, ("logic-in", "logic-gnd", "load-in", "load-out"), {"width": {"value": 26, "unit": "mm"}, "length": {"value": 34, "unit": "mm"}}, assumption_refs=("assumption-relay-logic-level",)),
            ComponentSpec("component-pump", "Water pump", "water delivery", "subsystem-water", "Low-voltage DC pump delivering water through tubing.", {"voltage_v": 5.0, "current_a": 0.8, "inductive_load": True}, ("power+", "ground", "inlet", "outlet"), {"width": {"value": 40, "unit": "mm"}, "length": {"value": 60, "unit": "mm"}}, assumption_refs=("assumption-pump-rating",)),
            ComponentSpec("component-reservoir", "Reservoir", "water storage", "subsystem-water", "Stores irrigation water away from exposed electronics.", {"capacity_l": 2.0}, ("outlet",), {"width": {"value": 120, "unit": "mm"}, "length": {"value": 180, "unit": "mm"}, "height": {"value": 150, "unit": "mm"}}, assumption_refs=("assumption-reservoir-size",)),
            ComponentSpec("component-tubing", "Tubing", "water routing", "subsystem-water", "Flexible tube between reservoir, pump, and plant.", {"inner_diameter_mm": 6}, ("end-a", "end-b"), {"length": {"value": 1, "unit": "m"}}, assumption_refs=("assumption-tube-fit",)),
            ComponentSpec("component-power", "5 V DC power source", "system power", "subsystem-power", "Isolated low-voltage supply for controller and pump.", {"voltage_v": 5.0, "available_current_a": 2.0, "mains_exposed": False}, ("5v", "ground"), {"width": {"value": 45, "unit": "mm"}, "length": {"value": 70, "unit": "mm"}}, assumption_refs=("assumption-certified-adapter",)),
            ComponentSpec("component-enclosure", "Electronics enclosure", "water separation", "subsystem-structure", "Splash-resistant enclosure for controller, driver, and power connections.", {"waterproofing": "splash-resistant", "contains": ["component-esp32", "component-driver"]}, ("cable-gland",), {"width": {"value": 100, "unit": "mm"}, "length": {"value": 120, "unit": "mm"}, "height": {"value": 60, "unit": "mm"}}, assumption_refs=("assumption-waterproof-enclosure",)),
        )
        connections = (
            ConnectionSpec("connection-sensor-signal", "component-sensor", "component-esp32", "signal", "gpio-sensor", "signal", "Sensor measurement to controller."),
            ConnectionSpec("connection-esp32-driver", "component-esp32", "component-driver", "gpio-pump", "logic-in", "control", "GPIO controls the isolated driver."),
            ConnectionSpec("connection-driver-pump", "component-driver", "component-pump", "load-out", "power+", "switched-power", "Driver switches pump power."),
            ConnectionSpec("connection-power-driver", "component-power", "component-driver", "5v", "load-in", "power", "Supply feeds pump driver."),
            ConnectionSpec("connection-power-esp32", "component-power", "component-esp32", "5v", "3v3", "regulated-power", "Board regulator supplies ESP32."),
            ConnectionSpec("connection-common-ground", "component-power", "component-esp32", "ground", "gnd", "ground", "Common logic reference."),
            ConnectionSpec("connection-reservoir-tube", "component-reservoir", "component-tubing", "outlet", "end-a", "fluid", "Tubing draws from reservoir."),
            ConnectionSpec("connection-tube-pump", "component-tubing", "component-pump", "end-b", "inlet", "fluid", "Tubing connects to pump inlet."),
        )
        entities = [PlannedEntity(project_id, EntityKind.PROJECT, "Automatic Irrigation System", metadata=(("objective", request.objective),))]
        entities += [PlannedEntity(s.id, EntityKind.SUBSYSTEM, s.name, project_id, (("role", s.role), ("description", s.description))) for s in subsystems]
        entities += [PlannedEntity(c.id, EntityKind.COMPONENT, c.name, c.subsystem_id, tuple({
            "role": c.role, "description": c.description, "parameters": c.parameters,
            "interfaces": list(c.interfaces), "dimensions": c.dimensions,
            "representation_status": c.representation_status,
            "evidence_refs": list(c.evidence_refs), "assumption_refs": list(c.assumption_refs),
        }.items())) for c in components]
        for i, text in enumerate(request.requirements): entities.append(PlannedEntity(f"requirement-{i+1}", EntityKind.REQUIREMENT, text, project_id))
        for i, text in enumerate(request.assumptions): entities.append(PlannedEntity(f"assumption-{i+1}", EntityKind.ASSUMPTION, text, project_id))
        referenced_assumptions = sorted({ref for component in components for ref in component.assumption_refs})
        referenced_evidence = sorted({ref for component in components for ref in component.evidence_refs})
        entities += [PlannedEntity(ref, EntityKind.ASSUMPTION, ref.removeprefix("assumption-").replace("-", " ").title(), project_id) for ref in referenced_assumptions]
        entities += [PlannedEntity(ref, EntityKind.EVIDENCE, "ESP32 manufacturer datasheet reference", project_id, (("source_status", "source_required"),)) for ref in referenced_evidence]
        entities += [PlannedEntity(f"constraint-{i+1}", EntityKind.CONSTRAINT, text, project_id) for i, text in enumerate(("Use low-voltage DC only", "Separate water from electronics"))]
        entities += [PlannedEntity(c.id, EntityKind.CONNECTION, c.description, project_id, tuple({
            "source_id": c.source_id, "target_id": c.target_id,
            "source_interface": c.source_interface, "target_interface": c.target_interface,
            "connection_type": c.connection_type,
        }.items())) for c in connections]
        operations = [GraphOperation(PatchOperation.ADD_ENTITY, entity=EngineeringEntity(
            id=e.id, kind=e.kind, name=e.name, parent_id=e.parent_id, metadata=dict(e.metadata),
            source_refs=tuple(dict(e.metadata).get("evidence_refs", [])) + tuple(dict(e.metadata).get("assumption_refs", [])))) for e in entities]
        relationships = tuple(PlannedRelationship(c.id + "-edge", c.source_id, c.target_id, c.connection_type) for c in connections)
        operations += [GraphOperation(PatchOperation.ADD_RELATIONSHIP, relationship=Relationship(id=r.id, source_id=r.source_id, target_id=r.target_id, type=r.type, metadata={"connection_id": r.id.removesuffix("-edge")})) for r in relationships]
        patch = GraphPatch("patch-auto-irrigation-v1", tuple(operations), "Create verified automatic irrigation project")
        plan = ProjectPlan(request, tuple(entities), relationships, patch,
            (RepresentationRequest(project_id, "system_diagram"),), VerificationRequest(patch.id, ("structure", "electrical", "physical", "safety")),
            (WorkspaceEventProposal("project.started", project_id),), subsystems, components, connections,
            ("Use low-voltage DC only", "Separate water from electronics"))
        plan.validate()
        return plan

    def propose_mosfet_replacement(self, graph):
        driver = next((entity for entity in graph.find(kind=EntityKind.COMPONENT)
                       if entity.metadata.get("family", entity.metadata.get("role")) in {"mosfet_driver", "motor_driver", "relay"}
                       or "driver" in str(entity.metadata.get("role", "")).lower()
                       or "driver_type" in entity.metadata.get("parameters", {})), None)
        if driver is None:
            raise ValueError("no compatible driver component")
        metadata = dict(driver.metadata)
        metadata.update({"role": "pump switching", "parameters": {"logic_voltage_v": 3.3, "load_voltage_v": 5.0, "max_current_a": 3.0, "driver_type": "logic-level-mosfet", "flyback_protection": True}, "description": "Logic-level MOSFET driver with flyback diode."})
        operations = [GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=driver.id, changes={"name": "Logic-level MOSFET driver", "metadata": metadata, "verification_status": "conceptual"})]
        for relationship in graph.relationships.values():
            if driver.id not in {relationship.source_id, relationship.target_id}:
                continue
            relationship_metadata = dict(relationship.metadata)
            relationship_metadata["driver_type"] = "logic-level-mosfet"
            operations.append(GraphOperation(PatchOperation.UPDATE_RELATIONSHIP, target_id=relationship.id, changes={"metadata": relationship_metadata}))
        return GraphPatch("patch-relay-to-mosfet", tuple(operations), f"Upgrade {driver.name} to a logic-level MOSFET driver", graph.current_revision_id)

    @staticmethod
    def _id(project_name: str, role: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
        return f"{role}-{uuid5(NAMESPACE_URL, f'aura:{normalized}:{role}').hex}"
