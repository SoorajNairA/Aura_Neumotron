import re

from aura.verification.catalogue import CATALOGUE

FAN_PARTS = ("esp32-devkit-v1", "ds18b20-module", "logic-mosfet-module", "dc-fan-5v",
             "resistor-4k7", "1n4007-diode", "supply-usb-5v-1a")
BY_ID = {item.component_definition_id: item for item in CATALOGUE}


def test_fan_parts_have_dated_prices():
    priced = 0
    for part in FAN_PARTS:
        price = BY_ID[part].to_dict()["price"]
        if price is None:
            continue
        priced += 1
        assert price["usd"] > 0
        assert price["source"].startswith("https://")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", price["retrieved"])
    assert priced >= 5


def test_unpriced_parts_have_no_price():
    assert BY_ID["mg996r-servo"].to_dict()["price"] is None
    assert BY_ID["dc-fan-5v"].to_dict()["price"] is None
