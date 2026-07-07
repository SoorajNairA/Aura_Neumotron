from __future__ import annotations

import re
from uuid import NAMESPACE_URL, uuid5

from aura.engineering_graph.model import EngineeringEntity, EntityKind, Relationship
from aura.engineering_graph.patches import GraphOperation, GraphPatch, PatchOperation
from aura.capabilities import CapabilityStatus, classify_objective

from .schemas import (
    ComponentSpec, ConnectionSpec, PlannedEntity, PlannedRelationship, ProjectPlan, ProjectRequest, SubsystemSpec,
    RepresentationRequest, VerificationRequest, WorkspaceEventProposal,
)


class PlannerService:
    """Produce a deterministic, structured proposal without executing it."""

    def plan(self, request: ProjectRequest) -> ProjectPlan:
        request.validate()
        capability=classify_objective(request.objective)
        if capability["status"] in {CapabilityStatus.UNSUPPORTED.value,CapabilityStatus.NEEDS_CLARIFICATION.value}:
            raise ValueError(capability)
        if "irrigation" in request.objective.lower() or ("soil" in request.objective.lower() and "pump" in request.objective.lower()):
            return self._irrigation_plan(request)
        if not request.components and any(word in request.objective.lower() for word in ("fan","feeder","weather","humidity","pressure","tank","servo","lid")):
            return self._mechatronic_plan(request,capability["status"])
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

    def _mechatronic_plan(self,request:ProjectRequest,capability_status:str)->ProjectPlan:
        text=request.objective.lower();project_id=self._id(request.objective,"project")
        families=["controller","power","enclosure"]
        if "fan" in text: families += ["temperature-sensor","driver","fan"]
        elif "feeder" in text: families += ["servo","container","dispensing-mechanism"]
        elif any(word in text for word in ("weather","humidity","pressure")): families += ["environmental-sensor"]
        elif "tank" in text: families += ["distance-sensor","indicator","container"]
        elif "servo" in text or "lid" in text: families += ["servo","lid","hinge","mounting-plate"]
        specs={
          "controller":("Controller board","microcontroller_board","electronics",{"logic_voltage_v":3.3,"gpio_max_current_ma":12},(52,28,8)),
          "power":("Low-voltage power source","low_voltage_power_source","power",{"voltage_v":5.0,"available_current_a":3.0,"mains_exposed":False},(48,30,18)),
          "enclosure":("Protective enclosure","enclosure","structure",{"contains":["component-controller"],"waterproofing":"splash-resistant" if "tank" in text else "basic"},(120,90,55)),
          "temperature-sensor":("Temperature sensor","temperature_sensor","sensor",{"supply_voltage_v":3.3,"signal_voltage_v":3.3,"threshold_c":26},(22,16,6)),
          "environmental-sensor":("Temperature humidity pressure sensor","environmental_sensor","sensor",{"supply_voltage_v":3.3,"measurements":["temperature","humidity","pressure"]},(24,18,6)),
          "distance-sensor":("Tank level distance sensor","distance_sensor","sensor",{"supply_voltage_v":5.0,"wet_environment":True},(45,22,18)),
          "driver":("Logic-level MOSFET driver","mosfet_driver","electronics",{"logic_voltage_v":3.3,"load_voltage_v":5.0,"max_current_a":3.0,"flyback_protection":True},(32,24,8)),
          "fan":("Desk fan","fan","actuator",{"voltage_v":5.0,"current_a":0.5,"inductive_load":True},(90,30,90)),
          "servo":("Small servo","servo","actuator",{"voltage_v":5.0,"current_a":0.8,"inductive_load":False},(40,20,38)),
          "container":("Container","container","mechanical",{"capacity_l":1.5,"wet_environment":"tank" in text},(110,100,150)),
          "dispensing-mechanism":("Conceptual dispensing wheel","generic_mechanical_part","mechanical",{"validation":"conceptual"},(55,55,25)),
          "indicator":("Low-voltage indicator","indicator","electronics",{"voltage_v":3.3},(18,12,8)),
          "lid":("Lightweight lid","lid","mechanical",{"mass_g":120},(120,90,6)),
          "hinge":("Lid hinge","hinge","mechanical",{"relationship":"revolute_proxy"},(80,10,10)),
          "mounting-plate":("Mounting plate","mounting_plate","structure",{},(150,100,6)),
        }
        subsystems=tuple(SubsystemSpec(f"subsystem-{role}",role.title(),role,"Deterministic semantic subsystem.") for role in dict.fromkeys(specs[f][2] for f in families))
        components=[]
        for family in families:
            name,kind,role,params,dims=specs[family];cid=f"component-{family}"
            components.append(ComponentSpec(cid,name,kind,f"subsystem-{role}",f"{name} for the requested low-voltage system.",params,("power","ground","signal"),{key:{"value":value,"unit":"mm"} for key,value in zip(("width","length","height"),dims)},assumption_refs=(f"assumption-{family}",)))
        ids={c.id for c in components};connections=[]
        def connect(a,b,kind):
            if a in ids and b in ids: connections.append(ConnectionSpec(f"connection-{a[10:]}-{b[10:]}-{kind}",a,b,"signal","signal",kind,f"{kind.title()} connection."))
        for sensor in ("component-temperature-sensor","component-environmental-sensor","component-distance-sensor"):connect(sensor,"component-controller","signal")
        for load in ("component-fan","component-servo"): connect("component-driver" if "component-driver" in ids else "component-controller",load,"switched-power" if "component-driver" in ids else "control")
        connect("component-controller","component-driver","control")
        for target in sorted(ids-{"component-power","component-enclosure","component-container","component-lid","component-hinge","component-mounting-plate","component-dispensing-mechanism"}):connect("component-power",target,"power");connect("component-power",target,"ground")
        connect("component-servo","component-dispensing-mechanism","mechanical");connect("component-servo","component-lid","mechanical");connect("component-hinge","component-lid","mechanical")
        entities=[PlannedEntity(project_id,EntityKind.PROJECT,request.project_name,metadata=(("objective",request.objective),("capability_status",capability_status)))]
        entities += [PlannedEntity(s.id,EntityKind.SUBSYSTEM,s.name,project_id,(("role",s.role),)) for s in subsystems]
        entities += [PlannedEntity(c.id,EntityKind.COMPONENT,c.name,c.subsystem_id,tuple({"role":c.role,"family":c.role,"parameters":c.parameters,"interfaces":list(c.interfaces),"dimensions":c.dimensions,"representation_status":"placeholder","assumption_refs":list(c.assumption_refs)}.items())) for c in components]
        entities += [PlannedEntity(f"assumption-{i}",EntityKind.ASSUMPTION,value,project_id) for i,value in enumerate(("Use 5 V isolated low-voltage power","Exact mechanical fit remains conceptual"),1)]
        entities += [PlannedEntity(c.id,EntityKind.CONNECTION,c.description,project_id,tuple({"source_id":c.source_id,"target_id":c.target_id,"connection_type":c.connection_type}.items())) for c in connections]
        operations=[GraphOperation(PatchOperation.ADD_ENTITY,entity=EngineeringEntity(e.id,e.kind,e.name,e.parent_id,dict(e.metadata))) for e in entities]
        relationships=tuple(PlannedRelationship(c.id+"-edge",c.source_id,c.target_id,c.connection_type) for c in connections)
        operations += [GraphOperation(PatchOperation.ADD_RELATIONSHIP,relationship=Relationship(r.id,r.source_id,r.target_id,r.type,{"connection_id":r.id.removesuffix("-edge")})) for r in relationships]
        patch=GraphPatch(self._id(request.objective,"initial-patch"),tuple(operations),f"Create {request.project_name}")
        plan=ProjectPlan(request,tuple(entities),relationships,patch,(RepresentationRequest(project_id,"system_diagram"),),VerificationRequest(patch.id,("structure","electrical","physical","safety")),(WorkspaceEventProposal("project.started",project_id),),subsystems,tuple(components),tuple(connections),("Use low-voltage DC only","Unsupported certification remains explicit"))
        plan.validate();return plan

    def _irrigation_plan(self, request: ProjectRequest) -> ProjectPlan:
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
        driver = graph.get("component-driver")
        metadata = dict(driver.metadata)
        metadata.update({"role": "pump switching", "parameters": {"logic_voltage_v": 3.3, "load_voltage_v": 5.0, "max_current_a": 3.0, "driver_type": "logic-level-mosfet", "flyback_protection": True}, "description": "Logic-level MOSFET driver with flyback diode."})
        operations = [GraphOperation(PatchOperation.UPDATE_ENTITY, target_id=driver.id, changes={"name": "Logic-level MOSFET driver", "metadata": metadata, "verification_status": "conceptual"})]
        for relationship_id in ("connection-esp32-driver-edge", "connection-driver-pump-edge"):
            relationship = graph.relationships[relationship_id]
            relationship_metadata = dict(relationship.metadata)
            relationship_metadata["driver_type"] = "logic-level-mosfet"
            operations.append(GraphOperation(PatchOperation.UPDATE_RELATIONSHIP, target_id=relationship_id, changes={"metadata": relationship_metadata}))
        return GraphPatch("patch-relay-to-mosfet", tuple(operations), "Relay driver -> Logic-level MOSFET driver (stable component-driver)", graph.current_revision_id)

    @staticmethod
    def _id(project_name: str, role: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")
        return f"{role}-{uuid5(NAMESPACE_URL, f'aura:{normalized}:{role}').hex}"
