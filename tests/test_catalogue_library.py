import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aura.verification import pins as pins_module
from aura.verification.catalogue import BY_ID, CATALOGUE
from aura.verification.pins import CATEGORIES, ROLES, pins_for_definition
from aura.workspace.server import create_app

FRONTEND_SRC = Path(__file__).resolve().parents[1] / "src" / "aura" / "workspace" / "web" / "frontend" / "src"


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        yield client


def test_every_part_has_category_pins_source_and_known_roles():
    for d in CATALOGUE:
        assert d.category in CATEGORIES, d.component_definition_id
        assert d.evidence_ids, d.component_definition_id
        assert all(p.role in ROLES for p in d.pins), d.component_definition_id
        if d.family not in {"enclosure", "breadboard", "terminal_block"}:
            assert d.pins, d.component_definition_id


def test_new_categories_filled():
    by_cat = {c: [d for d in CATALOGUE if d.category == c] for c in CATEGORIES}
    assert {d.component_definition_id for d in by_cat["displays"]} >= {"ssd1306-oled-128x64", "lcd1602-i2c", "max7219-matrix", "ws2812b-stick-8"}
    assert {d.component_definition_id for d in by_cat["communication"]} >= {"rfm95w-lora", "nrf24l01-plus", "neo6m-gps", "mfrc522-rfid"}


def test_only_devkit_is_full_board():
    boards = [d for d in CATALOGUE if d.category == "boards"]
    assert {d.component_definition_id for d in boards if d.support == "full"} == {"esp32-devkit-v1"}


def test_bme280_overrides_signal_with_i2c_pins():
    roles = {p.label: p.role for p in BY_ID["bme280-i2c-module"].pins}
    assert roles["SDA"] == "i2c_sda" and roles["SCL"] == "i2c_scl"


def test_ds18b20_threshold_setting_range():
    assert BY_ID["ds18b20-module"].settings["threshold_c"] == {"min": -55.0, "max": 125.0}


def test_api_filters_by_category(client):
    items = client.get("/api/catalogue", params={"category": "displays"}).json()
    assert items and all(i["category"] == "displays" for i in items)
    assert {"pins", "settings", "support"} <= set(items[0])


def test_override_pin_names_and_roles():
    names = lambda i: {p.name: (p.label, p.role) for p in BY_ID[i].pins}
    assert names("ssd1306-oled-128x64")["sda"] == ("SDA", "i2c_sda") and "signal" not in names("ssd1306-oled-128x64")
    assert names("max7219-matrix")["mosi"] == ("DIN", "spi_mosi") and names("max7219-matrix")["sck"][0] == "CLK" and "miso" not in names("max7219-matrix")
    assert {"sck", "mosi", "miso", "cs"} <= set(names("mfrc522-rfid"))
    assert names("neo6m-gps")["tx"][1] == "uart_tx" and names("neo6m-gps")["rx"][1] == "uart_rx"
    assert names("ws2812b-stick-8")["din"] == ("DIN", "digital_in")
    assert names("ds18b20-module")["signal"] == ("DAT", "digital_out")


def test_overrides_and_settings_only_name_catalogue_parts():
    assert set(pins_module.PART_PIN_OVERRIDES) | set(pins_module.PART_SETTINGS) <= set(BY_ID)


def test_pin_labels_are_unique_per_part():
    for d in CATALOGUE:
        labels = [p.label for p in d.pins]
        assert len(labels) == len(set(labels)), (d.component_definition_id, labels)


def test_hc_sr04_has_trig_and_echo_not_sda():
    pins = {p.name: (p.label, p.role) for p in BY_ID["hc-sr04-class"].pins}
    assert pins["trig"] == ("TRIG", "digital_in") and pins["echo"] == ("ECHO", "digital_out") and "signal" not in pins


def test_family_template_roles_and_fallback():
    assert {p.name: p.role for p in pins_for_definition(None, "servo")}["signal"] == "pwm_in"
    assert {p.name: p.role for p in pins_for_definition("soil", "soil_moisture_sensor")}["signal"] == "analog_out"
    assert pins_for_definition("x", "no_such_family") == ()
    assert pins_for_definition("bh1750-module", "light_sensor") != pins_for_definition("photoresistor-module", "light_sensor")


def test_new_part_facts():
    assert BY_ID["pir-hc-sr501"].properties["logic_voltage"].value == 3.3
    assert BY_ID["lcd1602-i2c"].properties["logic_voltage"].value == 5.0
    assert BY_ID["lcd1602-i2c"].settings["i2c_address"] == {"choices": list(range(32, 40))}
    assert BY_ID["sg90-servo"].settings["min_angle"] == {"min": 0, "max": 180}
    assert BY_ID["breadboard-400"].family == "breadboard" and BY_ID["breadboard-400"].category == "breadboards"


def test_to_dict_carries_new_fields():
    d = BY_ID["ds18b20-module"].to_dict()
    assert d["category"] == "sensors" and d["support"] == "full"
    assert {"name", "label", "role", "voltageRange"} == set(d["pins"][0])
    assert d["settings"]["threshold_c"]["min"] == -55.0


def test_esp32_labels_match_pinout_ts():
    text = (FRONTEND_SRC / "pinout.ts").read_text(encoding="utf-8")
    headers = {label for block in ("J2", "J3") for label in re.findall(r'"([^"]+)"', re.search(rf"export const {block}=\[(.*?)\];", text, re.S).group(1))}
    for pin in BY_ID["esp32-devkit-v1"].pins:
        # power pins carry a printed header label; GPIO and bus ports are named by port and resolved from gpio_map at render time
        assert pin.label in headers or pin.label == pin.name, pin
        if pin.role in {"power_out", "power_in", "ground"}: assert pin.label in headers, pin


def test_fixture_is_current(tmp_path):
    out = tmp_path / "dump.json"
    assert pins_module.main(["--dump", str(out)]) == 0
    committed = FRONTEND_SRC / "catalogPins.fixture.json"
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(committed.read_text(encoding="utf-8"))
