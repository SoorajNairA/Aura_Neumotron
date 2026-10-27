import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aura.engineering_graph.serialization import graph_from_dict
from aura.firmware.compile import compile_sketch
from aura.firmware.generic import control_block, generate_generic_sketch
from aura.firmware.io import RANGES, IoPoint, default_rules, io_points
from aura.firmware.sketch import FirmwareUnsupported, generate_fan_sketch
from aura.workspace.server import create_app

PLANT = "Build an automatic plant watering system with a soil moisture sensor and a pump"
TABLE = json.loads((Path(__file__).parent / "fixtures" / "rule_truth_table.json").read_text(encoding="utf-8"))


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as c:
        yield c


def graph(client, objective, add=()):
    project_id = client.post("/api/projects", json={"objective": objective, "planningMode": "deterministic_test"}).json()["projectId"]
    if add:
        proposal = client.post(f"/api/projects/{project_id}/component-proposals", json={"baseRevision": 1, "componentDefinitionIds": list(add)}).json()
        assert client.post(f"/api/projects/{project_id}/modification-proposals/{proposal['proposalId']}/commit").status_code == 200
    return graph_from_dict(client.get(f"/api/projects/{project_id}/graph").json())


def plant_artifact(client, add=()):
    g = graph(client, PLANT, add)
    return generate_generic_sketch(g, default_rules(io_points(g)))


def test_plant_sketch_drives_soil_and_pump(client):
    artifact = plant_artifact(client)
    soil = artifact.pins["soil_1"]
    assert soil in (32, 33, 34, 35, 36, 39) and f"#define SOIL_1_PIN {soil}" in artifact.source
    assert "analogRead(SOIL_1_PIN)" in artifact.source and "// uncalibrated" in artifact.source
    assert f"#define PUMP_1_PIN {artifact.pins['pump_1']}" in artifact.source and "digitalWrite(PUMP_1_PIN" in artifact.source
    assert 'Serial.println("}");' in artifact.source and "\\\"rev\\\"" in artifact.source
    assert artifact.kind == "generic" and artifact.libraries == () and artifact.rules == tuple(default_rules(list(artifact.ios)))


def test_unsupported_part_is_left_out_and_reported(client):
    artifact = plant_artifact(client, add=["bme280-breakout"])
    assert "bme280" not in artifact.source.lower() and "BME280" not in artifact.source
    assert [io.definition_id for io in artifact.ios if not io.supported] == ["bme280-breakout"]


def test_no_supported_io_is_unsupported(client):
    g = graph(client, PLANT)
    for io in io_points(g):
        g.entities.pop(io.component_id)
    with pytest.raises(FirmwareUnsupported):
        generate_generic_sketch(g, [])


def test_fan_demo_sketch_unchanged(client):
    artifact = generate_fan_sketch(graph(client, "Build a temperature-controlled desk fan"))
    assert artifact.kind == "fan" and artifact.t_on_c == 26.0 and "bool fanControl(" in artifact.source


def case_ios(case):
    outputs = {rule["output"] for rule in case["rules"]}
    return [IoPoint(name, name, name, None, "output" if name in outputs else "input", value, RANGES[value][2], RANGES[value][0], RANGES[value][1], None, True)
            for name, value in case["ios"].items()]


def _cpp(value):
    return "1" if value is True else "0" if value is False else str(value)


@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
def test_control_block_matches_truth_table(tmp_path):
    body, checks = ["#include <cstdio>"], []
    for n, case in enumerate(TABLE):
        body += [f"namespace case{n} {{", control_block(case_ios(case), case["rules"]), "}"]
        for s, step in enumerate(case["steps"]):
            for name, value in step["inputs"].items():
                checks.append(f"  case{n}::S.{name}_ok = {'false' if value is None else 'true'}; case{n}::S.{name} = {_cpp(0 if value is None else value)};")
            checks.append(f"  case{n}::control({int(step['t'] * 1000)}UL);")
            for name in step["expect"]:
                checks.append(f'  printf("{n} {s} {name} %g\\n", case{n}::S.{name});')
    source = tmp_path / "table.cpp"
    source.write_text("\n".join(body + ["int main() {", *checks, "  return 0;", "}"]), encoding="utf-8")
    exe = tmp_path / "table.exe"
    subprocess.run(["g++", "-std=c++11", "-o", str(exe), str(source)], check=True, capture_output=True)
    got = {tuple(line.split()[:3]): float(line.split()[3]) for line in subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.splitlines()}
    want = {(str(n), str(s), name): float(value) for n, case in enumerate(TABLE) for s, step in enumerate(case["steps"]) for name, value in step["expect"].items()}
    assert got == want


@pytest.mark.skipif(not os.environ.get("AURA_ARDUINO_CLI"), reason="set AURA_ARDUINO_CLI to compile with arduino-cli")
def test_plant_sketch_compiles_with_arduino_cli(client):
    result = compile_sketch(plant_artifact(client), timeout_s=600)
    assert result.status == "passed", result.raw_output[-2000:]


@pytest.mark.skipif(not os.environ.get("AURA_ARDUINO_CLI"), reason="set AURA_ARDUINO_CLI to compile with arduino-cli")
def test_every_driver_compiles_with_arduino_cli(client):
    parts = ["photoresistor-module", "pir-hc-sr501", "push-button", "relay-module-5v", "led-generic", "sg90-servo"]
    g = graph(client, "Build a temperature-controlled desk fan", add=parts)
    ios = io_points(g)
    assert {io.definition_id for io in ios if io.supported} >= {"ds18b20-module", "logic-mosfet-module", *parts}
    result = compile_sketch(generate_generic_sketch(g, default_rules(ios)), timeout_s=600)
    assert result.status == "passed", result.raw_output[-2000:]
