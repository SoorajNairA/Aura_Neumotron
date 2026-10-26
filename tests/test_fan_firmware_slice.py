from __future__ import annotations

from aura.verification import catalogue


def test_catalogue_has_ds18b20_with_dated_evidence_and_4k7_resistor():
    sensor = catalogue.get("ds18b20-module")
    assert sensor.family == "temperature_sensor"
    assert sensor.properties["supply_voltage_range"].value == [3.0, 5.5]
    assert catalogue.get("resistor-4k7").family == "resistor"
    record = next(r for r in catalogue.evidence_records() if r.evidence_id == "evidence-analog-ds18b20")
    assert record.source.startswith("https://") and "retrieved 2026-10-27" in record.source_version
