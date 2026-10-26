from __future__ import annotations

from aura.verification import catalogue


def test_catalogue_has_ds18b20_with_dated_evidence_and_4k7_resistor():
    sensor = catalogue.get("ds18b20-module")
    assert sensor.family == "temperature_sensor"
    assert sensor.properties["supply_voltage_range"].value == [3.0, 5.5]
    assert catalogue.get("resistor-4k7").family == "resistor"
    record = next(r for r in catalogue.evidence_records() if r.evidence_id == "evidence-analog-ds18b20")
    assert record.source.startswith("https://") and "retrieved 2026-10-27" in record.source_version


from aura.planner.schemas import ProjectRequest
from aura.planner.service import PlannerService
from aura.verification.service import VerificationService

FAN_OBJECTIVE = "Design a temperature-controlled desk fan"


def _fan_plan(objective: str = FAN_OBJECTIVE):
    return PlannerService().plan(ProjectRequest("Fan", objective, ("Cool the desk",),
        components=("microcontroller_board", "temperature_sensor", "fan", "mosfet_driver", "low_voltage_power_source")))


def _role(plan, role):
    return next(component for component in plan.components if component.role == role)


def test_fan_plan_powers_ds18b20_from_logic_rail_with_pullup():
    plan = _fan_plan()
    sensor, controller = _role(plan, "temperature_sensor"), _role(plan, "microcontroller_board")
    assert sensor.parameters["component_definition_id"] == "ds18b20-module"
    pullups = [c for c in plan.components if c.role == "resistor" and "pull_up" in c.parameters["functional_roles"]]
    assert len(pullups) == 1 and pullups[0].parameters["resistance_ohm"] == 4700
    edges = {(x.source_id, x.source_interface, x.target_id, x.target_interface) for x in plan.connections}
    assert (controller.id, "vcc-out", sensor.id, "power") in edges
    assert (sensor.id, "signal", pullups[0].id, "terminal-a") in edges
    assert (pullups[0].id, "terminal-b", controller.id, "vcc-out") in edges
    # The 5 V rail must not reach the DS18B20, or its pulled-up data line would drive 5 V into an ESP32 GPIO.
    assert not any(x.target_id == sensor.id and x.target_interface == "power" and x.source_id != controller.id for x in plan.connections)
    assert VerificationService().verify(plan).accepted


from dataclasses import replace


def _controller_interface_to(plan, role):
    target = _role(plan, role).id
    controller = _role(plan, "microcontroller_board").id
    for edge in plan.connections:
        if {edge.source_id, edge.target_id} == {controller, target} and edge.connection_type in {"signal", "control"}:
            return edge.source_interface if edge.source_id == controller else edge.target_interface
    raise AssertionError(f"no controller signal edge to {role}")


def _with_gpio_map(plan, gpio_map):
    components = tuple(replace(c, parameters={**c.parameters, "gpio_map": gpio_map}) if c.role == "microcontroller_board" else c
                       for c in plan.components)
    return replace(plan, components=components)


def test_fan_plan_assigns_gpio4_sensor_and_gpio16_gate():
    plan = _fan_plan()
    gpio = _role(plan, "microcontroller_board").parameters["gpio_map"]
    assert gpio[_controller_interface_to(plan, "temperature_sensor")] == 4
    assert gpio[_controller_interface_to(plan, "mosfet_driver")] == 16


def test_gpio_check_rejects_duplicate_strapping_and_input_only_pins():
    plan = _fan_plan()
    sensor_if, gate_if = _controller_interface_to(plan, "temperature_sensor"), _controller_interface_to(plan, "mosfet_driver")
    for bad in ({sensor_if: 4, gate_if: 4}, {sensor_if: 4, gate_if: 0}, {sensor_if: 4, gate_if: 34}, {sensor_if: 7, gate_if: 16}):
        result = VerificationService().verify(_with_gpio_map(plan, bad))
        assert any(f.check == "ELEC_GPIO" and f.state.value == "failed" for f in result.findings), bad
    assert not any(f.check == "ELEC_GPIO" for f in VerificationService().verify(plan).findings if f.state.value == "failed")
