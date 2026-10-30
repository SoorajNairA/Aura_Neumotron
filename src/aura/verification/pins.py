"""Pin templates, categories and configurable settings for the curated catalogue.

`PinDefinition.name` is the engineering-graph interface name; `label` is the text printed on the part.
Pins are defined once per family; a part replaces only its `signal` pin where it differs (I2C, SPI, UART...).
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROLES = ("power_in", "power_out", "ground", "digital_in", "digital_out", "analog_out", "pwm_in", "i2c_sda", "i2c_scl",
         "spi_sck", "spi_mosi", "spi_miso", "spi_cs", "uart_tx", "uart_rx", "passive")
CATEGORIES = ("boards", "sensors", "actuators", "displays", "communication", "power", "breadboards", "basic")


@dataclass(frozen=True)
class PinDefinition:
    name: str
    label: str
    role: str
    voltage_range: tuple[float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "label": self.label, "role": self.role,
                "voltageRange": list(self.voltage_range) if self.voltage_range else None}


def _pin(name: str, label: str, role: str, voltage_range: tuple[float, float] | None = None) -> PinDefinition:
    return PinDefinition(name, label, role, voltage_range)


def _supply(vcc: str = "VCC", gnd: str = "GND") -> tuple[PinDefinition, ...]:
    return _pin("power", vcc, "power_in"), _pin("ground", gnd, "ground")


def _sensor(label: str, role: str, vcc: str = "VCC") -> tuple[PinDefinition, ...]:
    return (*_supply(vcc), _pin("signal", label, role))


_PASSIVE = (_pin("terminal-a", "A", "passive"), _pin("terminal-b", "B", "passive"))
_ESP32 = (_pin("vcc-out", "3V3", "power_out", (3.0, 3.6)), _pin("power", "5V", "power_out", (4.75, 5.25)), _pin("ground", "GND", "ground"),
          _pin("i2c-sda", "i2c-sda", "i2c_sda"), _pin("i2c-scl", "i2c-scl", "i2c_scl"), _pin("spi-sck", "spi-sck", "spi_sck"),
          _pin("spi-mosi", "spi-mosi", "spi_mosi"), _pin("spi-miso", "spi-miso", "spi_miso"),
          *(_pin(f"signal-{n}", f"signal-{n}", "digital_out") for n in range(1, 17)))

# Labels for families that already exist match the printed pin names in the 3D models (wiring3d.ts INTERFACE_PINS).
FAMILY_PINS: dict[str, tuple[PinDefinition, ...]] = {
    "microcontroller_board": _ESP32,
    "temperature_sensor": _sensor("DAT", "digital_out"), "environmental_sensor": _sensor("SDA", "digital_out"),
    "distance_sensor": _sensor("SDA", "digital_out"), "orientation_sensor": _sensor("SDA", "digital_out"),
    "soil_moisture_sensor": _sensor("AOUT", "analog_out"), "light_sensor": _sensor("AO", "analog_out"),
    "motion_sensor": _sensor("OUT", "digital_out"),
    "fan": _supply("+", "-"), "small_dc_pump": _supply("+", "-"), "small_dc_motor": _supply("+", "-"),
    "servo": (_pin("signal", "SIG", "pwm_in"), *_supply("V+")), "motor_driver": (*_supply(), _pin("signal", "IN", "digital_in"), _pin("load-output", "OUT", "power_out")),
    "mosfet_driver": (*_supply("V+", "V-"), _pin("signal", "IN", "digital_in"), _pin("load-output", "OUT+", "power_out")),
    "relay_module": (*_supply(), _pin("signal", "IN", "digital_in"), _pin("load-output", "NO", "power_out")),
    "flyback_diode": (_pin("anode", "A", "passive"), _pin("cathode", "K", "passive")),
    "resistor": _PASSIVE, "capacitor": _PASSIVE,
    "indicator": (_pin("signal", "A", "digital_in"), _pin("power", "A", "power_in"), _pin("ground", "K", "ground")),
    "switch": (_pin("signal", "1", "digital_out"), _pin("ground", "2", "ground")),
    "low_voltage_power_source": (_pin("power", "+", "power_out"), _pin("ground", "-", "ground")),
    "battery": (_pin("power", "+", "power_out"), _pin("ground", "-", "ground")),
    "buck_converter": (_pin("power", "VIN", "power_in"), _pin("ground", "GND", "ground"), _pin("vcc-out", "VOUT", "power_out")),
    "ldo_regulator": (_pin("power", "VIN", "power_in"), _pin("ground", "GND", "ground"), _pin("vcc-out", "VOUT", "power_out")),
    "battery_charger": (_pin("power", "IN+", "power_in"), _pin("ground", "GND", "ground"), _pin("vcc-out", "BAT+", "power_out")),
    "potentiometer": (_pin("power", "1", "power_in"), _pin("ground", "3", "ground"), _pin("signal", "W", "analog_out")),
    "buzzer": (*_supply(), _pin("signal", "I/O", "digital_in")),
    "oled_display": _sensor("SDA", "i2c_sda"), "character_display": _sensor("SDA", "i2c_sda"),
    "led_matrix": _sensor("DIN", "spi_mosi"), "addressable_led": _sensor("DIN", "digital_in", "5V"),
    "bluetooth_module": _sensor("TX", "uart_tx"), "lora_module": _sensor("MOSI", "spi_mosi", "3.3V"),
    "rf_module": _sensor("MOSI", "spi_mosi", "3.3V"), "gps_module": _sensor("TX", "uart_tx"), "rfid_module": _sensor("MOSI", "spi_mosi", "3.3V"),
    "enclosure": (), "breadboard": (), "terminal_block": (),
}
# Each of these keeps `power`/`ground` from its family and swaps the single `signal` pin for the pins listed.
_I2C = (_pin("sda", "SDA", "i2c_sda"), _pin("scl", "SCL", "i2c_scl"))
_UART = (_pin("tx", "TX", "uart_tx"), _pin("rx", "RX", "uart_rx"))


def _spi(cs: str = "CS", miso: bool = True, sck: str = "SCK", mosi: str = "MOSI") -> tuple[PinDefinition, ...]:
    return (_pin("sck", sck, "spi_sck"), _pin("mosi", mosi, "spi_mosi"), *((_pin("miso", "MISO", "spi_miso"),) if miso else ()), _pin("cs", cs, "spi_cs"))


PART_PIN_OVERRIDES: dict[str, tuple[PinDefinition, ...]] = {
    **{part: _I2C for part in ("bme280-breakout", "bme280-i2c-module", "aht20-module", "bh1750-module", "mpu6050-module", "vl53l0x-module",
                               "ssd1306-oled-128x64", "lcd1602-i2c")},
    "max7219-matrix": _spi(miso=False, sck="CLK", mosi="DIN"), "rfm95w-lora": _spi("NSS"), "nrf24l01-plus": _spi("CSN"), "mfrc522-rfid": _spi(),
    "hc05-bluetooth": _UART, "neo6m-gps": _UART, "ws2812b-stick-8": (_pin("din", "DIN", "digital_in"),),
}

CATEGORY_BY_FAMILY: dict[str, str] = {
    **dict.fromkeys(("microcontroller_board",), "boards"),
    **dict.fromkeys(("temperature_sensor", "environmental_sensor", "distance_sensor", "soil_moisture_sensor", "light_sensor", "motion_sensor", "orientation_sensor"), "sensors"),
    **dict.fromkeys(("small_dc_pump", "fan", "small_dc_motor", "servo", "motor_driver", "mosfet_driver", "relay_module"), "actuators"),
    **dict.fromkeys(("oled_display", "character_display", "led_matrix", "addressable_led"), "displays"),
    **dict.fromkeys(("bluetooth_module", "lora_module", "rf_module", "gps_module", "rfid_module"), "communication"),
    **dict.fromkeys(("low_voltage_power_source", "buck_converter", "battery", "ldo_regulator", "battery_charger"), "power"),
    "breadboard": "breadboards",
    **dict.fromkeys(("flyback_diode", "resistor", "capacitor", "indicator", "switch", "terminal_block", "enclosure", "potentiometer", "buzzer"), "basic"),
}

_ANGLES = {"min_angle": {"min": 0, "max": 180}, "max_angle": {"min": 0, "max": 180}}
# Per-part configurable keys with datasheet ranges: {"min","max"} for a number, {"choices": [...]} for a fixed set.
PART_SETTINGS: dict[str, dict[str, dict]] = {
    "ds18b20-module": {"threshold_c": {"min": -55.0, "max": 125.0}},
    "sg90-servo": dict(_ANGLES), "mg996r-servo": dict(_ANGLES),
    "ssd1306-oled-128x64": {"i2c_address": {"choices": [60, 61]}}, "lcd1602-i2c": {"i2c_address": {"choices": list(range(32, 40))}},
    "bme280-breakout": {"i2c_address": {"choices": [118, 119]}}, "bme280-i2c-module": {"i2c_address": {"choices": [118, 119]}},
    "bh1750-module": {"i2c_address": {"choices": [35, 92]}}, "mpu6050-module": {"i2c_address": {"choices": [104, 105]}},
    "aht20-module": {"i2c_address": {"choices": [56]}}, "vl53l0x-module": {"i2c_address": {"choices": [41]}},
}


def pins_for_definition(definition_id: str | None, family: str) -> tuple[PinDefinition, ...]:
    """Family template, with the part's `signal` pin replaced where the part has its own pins."""
    template = FAMILY_PINS.get(family, ())
    override = PART_PIN_OVERRIDES.get(definition_id or "")
    if override is None: return template
    return tuple(replacement for pin in template for replacement in (override if pin.name == "signal" else (pin,)))


def dump() -> dict[str, Any]:
    return {"families": {family: {pin.name: pin.label for pin in pins} for family, pins in FAMILY_PINS.items()},
            "overrides": {part: {pin.name: pin.label for pin in pins} for part, pins in PART_PIN_OVERRIDES.items()}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump catalogue pin labels for the frontend consistency test.")
    parser.add_argument("--dump", required=True, help="path of the JSON file to write")
    args = parser.parse_args(argv)
    Path(args.dump).write_text(json.dumps(dump(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
