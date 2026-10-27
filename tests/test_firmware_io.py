import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.interfaces import ESP32_ADC1_GPIOS
from aura.engineering_graph.serialization import graph_from_dict
from aura.firmware.io import RULES_SCHEMA, RuleError, default_rules, io_points, validate_rules
from aura.workspace.server import create_app

PLANT = "Build an automatic plant watering system with a soil moisture sensor and a pump"
FAN = "Build a temperature-controlled desk fan"


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as c:
        yield c


def project(client, objective):
    return client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"}).json()["projectId"]


def graph(client, project_id):
    return graph_from_dict(client.get(f"/api/projects/{project_id}/graph").json())


def test_plant_io_points(client):
    ios = io_points(graph(client, project(client, PLANT)))
    assert [(i.id, i.role, i.value) for i in ios] == [("soil_1", "input", "percent"), ("pump_1", "output", "bool")]
    assert ios[0].gpio in ESP32_ADC1_GPIOS
    assert (ios[0].low, ios[0].high, ios[0].unit) == (0, 100, "%") and all(i.supported for i in ios)


def test_fan_io_points(client):
    ios = {i.id: i for i in io_points(graph(client, project(client, FAN)))}
    assert ios["temp_1"].value == "celsius" and (ios["temp_1"].low, ios["temp_1"].high) == (-55, 125) and ios["temp_1"].gpio == 4
    assert ios["fan_1"].role == "output" and ios["fan_1"].gpio == 16


def test_unsupported_part_is_listed(client):
    project_id = project(client, FAN)
    proposal = client.post(f"/api/projects/{project_id}/component-proposals", json={"baseRevision": 1, "componentDefinitionIds": ["bme280-breakout"]}).json()
    assert client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit").status_code == 200
    unsupported = [i for i in io_points(graph(client, project_id)) if not i.supported]
    assert [(i.definition_id, i.role) for i in unsupported] == [("bme280-breakout", None)]


def plant_ios(client):
    return io_points(graph(client, project(client, PLANT)))


RULE = {"input": "soil_1", "when": "below", "threshold": 30, "release": 45, "output": "pump_1", "onValue": True, "offValue": False, "minOnSeconds": 5}


@pytest.mark.parametrize("change,code", [
    ({"input": "rain_1"}, "UNKNOWN_IO"),
    ({"output": "soil_1"}, "WRONG_DIRECTION"),
    ({"input": "pump_1"}, "WRONG_DIRECTION"),
    ({"threshold": 130}, "OUT_OF_RANGE"),
    ({"onValue": 90}, "OUT_OF_RANGE"),
    ({"when": "on", "threshold": None, "release": None}, "BAD_CONDITION"),
    ({"threshold": None}, "BAD_CONDITION"),
    ({"release": 20}, "BAD_CONDITION"),
])
def test_rule_errors(client, change, code):
    with pytest.raises(RuleError) as error:
        validate_rules({"rules": [RULE | change]}, plant_ios(client))
    assert error.value.code == code


def test_valid_rules_pass_and_schema_names_fields(client):
    assert validate_rules({"rules": [RULE], "explanation": "water when dry"}, plant_ios(client)) == [RULE]
    assert set(RULES_SCHEMA["properties"]["rules"]["items"]["required"]) >= {"input", "when", "output", "onValue", "offValue"}


def test_plant_default_rules(client):
    assert default_rules(plant_ios(client)) == [RULE]
