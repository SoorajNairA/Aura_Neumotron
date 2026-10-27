import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.interfaces import ESP32_ADC1_GPIOS, ESP32_INPUT_ONLY_GPIOS, allocate_gpio
from aura.engineering_graph.serialization import graph_from_dict
from aura.verification.graph_rules import evaluate_graph
from aura.workspace.modifications import ESP32_STRAPPING_GPIOS
from aura.workspace.server import create_app

PLANT = "Build an automatic plant watering system with a soil moisture sensor and a pump"


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as c:
        yield c


def plan(client, objective):
    project = client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"}).json()
    graph = client.get(f"/api/projects/{project['projectId']}/graph").json()
    return project["projectId"], graph


def controller_map(graph):
    return next(e for e in graph["entities"] if e["id"] == "component-controller")["metadata"]["parameters"]["gpio_map"]


def port_of(graph, component_id):
    for e in graph["entities"]:
        m = e["metadata"]
        if e["kind"] == "connection" and component_id in (m.get("source_id"), m.get("target_id")) and "component-controller" in (m.get("source_id"), m.get("target_id")):
            return m["source_interface"] if m["source_id"] == "component-controller" else m["target_interface"]


def test_plant_soil_sensor_gets_adc1_pin_and_no_strapping_pin(client):
    _, graph = plan(client, PLANT)
    gpio = controller_map(graph)
    assert gpio[port_of(graph, "component-soil-sensor")] in ESP32_ADC1_GPIOS
    assert not set(gpio.values()) & set(ESP32_STRAPPING_GPIOS)


def test_fan_demo_keeps_its_pins(client):
    _, graph = plan(client, "Build a temperature-controlled desk fan")
    assert controller_map(graph) == {"signal-1": 4, "signal-2": 16}


def test_library_add_of_photoresistor_gets_adc1_pin(client):
    project_id, _ = plan(client, "Build a temperature-controlled desk fan")
    proposal = client.post(f"/api/projects/{project_id}/component-proposals", json={"baseRevision": 1, "componentDefinitionIds": ["photoresistor-module"]}).json()
    assert [op["gpio"] for op in proposal["operations"] if op["operation"] == "add_component"][0] in ESP32_ADC1_GPIOS


def test_outputs_never_get_input_only_pins():
    used = set()
    for _ in range(20):
        pin = allocate_gpio("relay_module", "relay-module-5v", used)
        if pin is None: break
        assert pin not in ESP32_INPUT_ONLY_GPIOS and pin not in ESP32_STRAPPING_GPIOS
        used.add(pin)
    assert allocate_gpio("relay_module", "relay-module-5v", used) is None


def test_digital_inputs_fall_back_to_input_only_pins():
    used = {4, 13, 14, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33}
    assert allocate_gpio("motion_sensor", "pir-hc-sr501", used) == 34


def test_analog_light_sensor_by_family_but_i2c_light_sensor_is_digital():
    assert allocate_gpio("light_sensor", None, set()) == 32
    assert allocate_gpio("light_sensor", "bh1750-module", set()) == 4


def test_analog_sensor_off_adc1_fails_elec_adc(client):
    _, graph = plan(client, PLANT)
    controller_map(graph)[port_of(graph, "component-soil-sensor")] = 17
    model = graph_from_dict(graph)
    findings = []
    evaluate_graph(model, lambda code, state, *a, **k: findings.append((code, state.value, k.get("blocking"))))
    assert ("ELEC_ADC", "FAILED", True) in [(c, s.upper(), b) for c, s, b in findings]
