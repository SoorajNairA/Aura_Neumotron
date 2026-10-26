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


import json
import shutil
import subprocess
from pathlib import Path

import pytest

from aura.engineering_graph.model import EngineeringGraph
from aura.engineering_graph.patches import apply_patch

CASES = json.loads((Path(__file__).parent / "fixtures" / "fan_hysteresis_cases.json").read_text())


def _graph(plan):
    return apply_patch(EngineeringGraph(plan.entities[0].id), plan.patch)


def test_sketch_uses_graph_pins_thresholds_and_revision():
    from aura.firmware import generate_fan_sketch
    graph = _graph(_fan_plan())
    artifact = generate_fan_sketch(graph)
    assert "#define ONE_WIRE_PIN 4" in artifact.source and "#define FAN_PIN 16" in artifact.source
    assert "#define T_ON_C 26.0" in artifact.source and "#define T_OFF_C 24.0" in artifact.source
    assert graph.current_revision_id in artifact.source and artifact.revision_id == graph.current_revision_id
    assert artifact.pins == {"temperature_data": 4, "fan_gate": 16} and artifact.fqbn == "esp32:esp32:esp32"
    assert "{{" not in artifact.source


def test_sketch_threshold_follows_objective():
    from aura.firmware import generate_fan_sketch
    artifact = generate_fan_sketch(_graph(_fan_plan("Design a desk fan that turns on above 30 °C")))
    assert (artifact.t_on_c, artifact.t_off_c) == (30.0, 28.0)
    assert "#define T_ON_C 30.0" in artifact.source and "#define T_OFF_C 28.0" in artifact.source


@pytest.mark.parametrize("objective,components", [
    ("Make a robotic arm", ("microcontroller_board", "servo", "low_voltage_power_source")),
    ("Design an Arduino Nano temperature-controlled desk fan", ("arduino nano", "temperature_sensor", "fan", "mosfet_driver")),
])
def test_unsupported_graphs_raise_firmware_unsupported(objective, components):
    from aura.firmware import FirmwareUnsupported, generate_fan_sketch
    plan = PlannerService().plan(ProjectRequest("X", objective, ("Do it",), components=components))
    with pytest.raises(FirmwareUnsupported) as error:
        generate_fan_sketch(_graph(plan))
    assert error.value.reasons


def test_cpp_rule_matches_truth_table(tmp_path):
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.skip("g++ is not installed; the C++ fan rule was not executed")
    from aura.firmware.sketch import TEMPLATE_PATH
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rule = template.split("// BEGIN fanControl")[1].split("// END fanControl")[0]
    rows = "".join(f"{{{str(p).lower()},{t if t is not None else 0},{'false' if t is None else 'true'},{str(e).lower()}}}," for p, t, e in CASES)
    harness = tmp_path / "harness.cpp"
    harness.write_text("#include <cstdio>\n" + rule + "struct Row{bool p;float t;bool v;bool e;};\nint main(){Row rows[]={" + rows +
                       "};int bad=0;for(auto r:rows) if(fanControl(r.p,r.t,r.v,26.0f,24.0f)!=r.e){std::printf(\"bad %d %f;\",r.p,r.t);bad++;}return bad;}\n")
    exe = tmp_path / "harness.exe"
    subprocess.run([compiler, "-std=c++11", str(harness), "-o", str(exe)], check=True, capture_output=True)
    result = subprocess.run([str(exe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
