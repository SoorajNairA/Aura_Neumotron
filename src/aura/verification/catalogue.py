from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .evidence import EvidenceKind, EvidenceRecord
from .pins import CATEGORY_BY_FAMILY, PART_SETTINGS, PinDefinition, pins_for_definition
from .units import in_range

CATALOGUE_VERSION = "catalogue-v1"


@dataclass(frozen=True)
class PropertyFact:
    value: Any
    unit: str | None
    evidence_id: str
    qualifier: str = "rated"

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "unit": self.unit, "evidenceId": self.evidence_id,
                "qualifier": self.qualifier}


@dataclass(frozen=True)
class ComponentDefinition:
    component_definition_id: str
    family: str
    manufacturer: str
    part_number: str
    properties: dict[str, PropertyFact]
    interfaces: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    representation: dict[str, Any]
    price: dict[str, Any] | None = None
    category: str = "basic"
    pins: tuple[PinDefinition, ...] = ()
    settings: dict[str, dict] = field(default_factory=dict)
    support: str = "full"

    def to_dict(self) -> dict[str, Any]:
        return {"componentDefinitionId": self.component_definition_id, "componentDefinitionVersion": CATALOGUE_VERSION, "family": self.family,
                "manufacturer": self.manufacturer, "partNumber": self.part_number,
                "properties": {k: v.to_dict() for k, v in self.properties.items()},
                "interfaces": list(self.interfaces), "evidenceIds": list(self.evidence_ids),
                "representation": self.representation, "price": self.price, "category": self.category,
                "pins": [pin.to_dict() for pin in self.pins], "settings": self.settings, "support": self.support}


_SOURCES = {
    "espressif": EvidenceRecord.curated("evidence-espressif-esp32", EvidenceKind.MANUFACTURER_DATASHEET,
        "ESP32 Series Datasheet", "https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf", "Espressif Systems", ("supply_voltage", "logic_voltage", "gpio_current"), "ESP32 datasheet"),
    "bosch": EvidenceRecord.curated("evidence-bosch-bme280", EvidenceKind.MANUFACTURER_DATASHEET,
        "BME280 Combined Humidity and Pressure Sensor", "https://www.bosch-sensortec.com/products/environmental-sensors/humidity-sensors-bme280/", "Bosch Sensortec", ("supply_voltage", "current"), "BME280"),
    "ti": EvidenceRecord.curated("evidence-ti-drivers", EvidenceKind.MANUFACTURER_DATASHEET,
        "Low-voltage motor and load driver technical documentation", "https://www.ti.com/motor-drivers/overview.html", "Texas Instruments", ("supply_voltage", "logic_voltage", "current")),
    "st": EvidenceRecord.curated("evidence-st-protection", EvidenceKind.MANUFACTURER_DATASHEET,
        "Discrete protection device documentation", "https://www.st.com/en/diodes-and-rectifiers.html", "STMicroelectronics", ("current", "reverse_voltage")),
    "adafruit": EvidenceRecord.curated("evidence-adafruit-modules", EvidenceKind.MANUFACTURER_PRODUCT_PAGE,
        "Low-voltage hobby module technical specifications", "https://www.adafruit.com/category/35", "Adafruit Industries", ("supply_voltage", "current", "dimensions")),
    "assumption": EvidenceRecord.curated("evidence-curated-component-assumptions", EvidenceKind.ENGINEERING_ASSUMPTION,
        "AURA bounded component-family assumptions", "aura://curated-assumptions/v1", "AURA", ("supply_voltage", "current", "dimensions"), "v1"),
    "dfrobot": EvidenceRecord.curated("evidence-dfrobot-sen0193", EvidenceKind.MANUFACTURER_PRODUCT_PAGE,
        "Capacitive Soil Moisture Sensor SEN0193", "https://wiki.dfrobot.com/Capacitive_Soil_Moisture_Sensor_SKU_SEN0193", "DFRobot", ("supply_voltage", "dimensions"), "SEN0193"),
    "stmicro-vl53": EvidenceRecord.curated("evidence-st-vl53l0x", EvidenceKind.MANUFACTURER_PRODUCT_PAGE,
        "VL53L0X time-of-flight ranging sensor", "https://www.st.com/en/imaging-and-photonics-solutions/vl53l0x.html", "STMicroelectronics", ("supply_voltage", "current", "dimensions"), "VL53L0X"),
    "arduino": EvidenceRecord.curated("evidence-arduino-uno", EvidenceKind.MANUFACTURER_PRODUCT_PAGE,
        "Arduino UNO R4 Minima technical specifications", "https://docs.arduino.cc/hardware/uno-r4-minima/", "Arduino", ("supply_voltage", "logic_voltage", "dimensions"), "UNO R4 Minima"),
    "analog-ds18b20": EvidenceRecord.curated("evidence-analog-ds18b20", EvidenceKind.MANUFACTURER_DATASHEET,
        "DS18B20 Programmable Resolution 1-Wire Digital Thermometer", "https://cdn.sparkfun.com/datasheets/Sensors/Temp/DS18B20.pdf", "Maxim Integrated (Analog Devices)",
        ("supply_voltage", "current", "accuracy"), "DS18B20 datasheet; retrieved 2026-10-27"),
    "solomon-ssd1306": EvidenceRecord.curated("evidence-solomon-ssd1306", EvidenceKind.MANUFACTURER_DATASHEET,
        "SSD1306 128x64 Dot Matrix OLED/PLED Segment/Common Driver with Controller", "https://cdn-shop.adafruit.com/datasheets/SSD1306.pdf", "Solomon Systech", ("supply_voltage", "current", "dimensions"), "SSD1306 datasheet; retrieved 2026-10-30"),
    "nxp-pcf8574": EvidenceRecord.curated("evidence-nxp-pcf8574", EvidenceKind.MANUFACTURER_DATASHEET,
        "PCF8574/PCF8574A Remote 8-bit I/O expander for I2C-bus", "https://www.nxp.com/docs/en/data-sheet/PCF8574_PCF8574A.pdf", "NXP Semiconductors", ("supply_voltage", "current", "logic_voltage", "dimensions"), "PCF8574 datasheet; retrieved 2026-10-30"),
    "analog-max7219": EvidenceRecord.curated("evidence-analog-max7219", EvidenceKind.MANUFACTURER_DATASHEET,
        "MAX7219/MAX7221 Serially Interfaced, 8-Digit LED Display Drivers", "https://www.analog.com/media/en/technical-documentation/data-sheets/MAX7219-MAX7221.pdf", "Analog Devices (Maxim Integrated)", ("supply_voltage", "current", "dimensions"), "MAX7219 datasheet; retrieved 2026-10-30"),
    "worldsemi-ws2812b": EvidenceRecord.curated("evidence-worldsemi-ws2812b", EvidenceKind.MANUFACTURER_DATASHEET,
        "WS2812B Intelligent control LED integrated light source", "https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf", "Worldsemi", ("supply_voltage", "current", "dimensions"), "WS2812B datasheet; retrieved 2026-10-30"),
    "hoperf-rfm95w": EvidenceRecord.curated("evidence-hoperf-rfm95w", EvidenceKind.MANUFACTURER_PRODUCT_PAGE,
        "RFM95W LoRa transceiver module", "https://www.hoperf.com/modules/lora/RFM95W.html", "HOPERF", ("supply_voltage", "current", "dimensions"), "RFM95W; retrieved 2026-10-30"),
    "nordic-nrf24": EvidenceRecord.curated("evidence-nordic-nrf24", EvidenceKind.MANUFACTURER_PRODUCT_PAGE,
        "nRF24 Series 2.4 GHz transceivers", "https://www.nordicsemi.com/Products/nRF24-series", "Nordic Semiconductor", ("supply_voltage", "current", "dimensions"), "nRF24L01+; retrieved 2026-10-30"),
    "ublox-neo6": EvidenceRecord.curated("evidence-ublox-neo6", EvidenceKind.MANUFACTURER_PRODUCT_PAGE,
        "u-blox 6 NEO-6 series GPS modules", "https://www.u-blox.com/en/product/neo-6-series", "u-blox", ("supply_voltage", "current", "dimensions"), "NEO-6M; retrieved 2026-10-30"),
    "nxp-mfrc522": EvidenceRecord.curated("evidence-nxp-mfrc522", EvidenceKind.MANUFACTURER_DATASHEET,
        "MFRC522 Standard performance MIFARE and NTAG frontend", "https://www.nxp.com/docs/en/data-sheet/MFRC522.pdf", "NXP Semiconductors", ("supply_voltage", "current", "dimensions"), "MFRC522 datasheet; retrieved 2026-10-30"),
    "ams-ams1117": EvidenceRecord.curated("evidence-ams-ams1117", EvidenceKind.MANUFACTURER_DATASHEET,
        "AMS1117 1 A low dropout voltage regulator", "http://www.advanced-monolithic.com/pdf/ds1117.pdf", "Advanced Monolithic Systems", ("supply_voltage", "current", "dimensions"), "AMS1117 datasheet; retrieved 2026-10-30"),
    "topower-tp4056": EvidenceRecord.curated("evidence-topower-tp4056", EvidenceKind.MANUFACTURER_DATASHEET,
        "TP4056 1 A standalone linear Li-ion battery charger", "https://dlnmh9ip6v2uc.cloudfront.net/datasheets/Prototyping/TP4056.pdf", "NanJing Top Power ASIC Corp.", ("supply_voltage", "current", "dimensions"), "TP4056 datasheet; retrieved 2026-10-30"),
    "bourns-ptv09": EvidenceRecord.curated("evidence-bourns-ptv09", EvidenceKind.MANUFACTURER_DATASHEET,
        "PTV09 9 mm rotary potentiometer", "https://www.bourns.com/docs/Product-Datasheets/ptv09.pdf", "Bourns", ("supply_voltage", "current", "dimensions"), "PTV09 datasheet; retrieved 2026-10-30"),
    "pui-ai1223": EvidenceRecord.curated("evidence-pui-ai1223", EvidenceKind.MANUFACTURER_PRODUCT_PAGE,
        "AI-1223-TWT-5V-R active buzzer", "https://www.puiaudio.com/products/ai-1223-twt-5v-r", "PUI Audio", ("supply_voltage", "current", "dimensions"), "AI-1223-TWT-5V-R; retrieved 2026-10-30"),
    "busboard-bb400": EvidenceRecord.curated("evidence-busboard-bb400", EvidenceKind.MANUFACTURER_PRODUCT_PAGE,
        "BB400 400-point solderless breadboard", "https://www.busboard.com/BB400", "BusBoard Prototype Systems", ("dimensions",), "BB400; retrieved 2026-10-30"),
}


def _p(value: Any, unit: str | None, evidence: str, qualifier: str = "rated") -> PropertyFact:
    return PropertyFact(value, unit, _SOURCES[evidence].evidence_id, qualifier)


def _definition(identifier: str, family: str, manufacturer: str, part: str, source: str,
                voltage=(3.0, 3.6), current_ma: float | None = None,
                dimensions: tuple[float, float, float] | None = None,
                interfaces: tuple[str, ...] = ("power", "ground", "signal")) -> ComponentDefinition:
    props = {"supply_voltage_range": _p(list(voltage), "V", source)}
    if current_ma is not None: props["current"] = _p(current_ma, "mA", source, "maximum")
    if dimensions is not None: props["dimensions"] = _p(list(dimensions), "mm", source)
    evidence = _SOURCES[source].evidence_id
    return ComponentDefinition(identifier, family, manufacturer, part, props, interfaces, (evidence,),
                               {"type": "proxy", "dimensionsProperty": "dimensions"})


# Deliberately small, reviewable catalogue: variants cover the six supported benchmark families.
_SPECS = (
 ("arduino-nano-v3","microcontroller_board","Arduino-compatible","Arduino Nano V3","assumption",(4.5,12),200,(45,18,8)),
 ("esp32-devkit-v1","microcontroller_board","Espressif","ESP32-DevKitC","espressif",(4.75,5.25),240,(28,52,12)),
 ("esp8266-nodemcu-v3","microcontroller_board","Espressif-compatible","NodeMCU ESP8266","assumption",(4.5,5.5),500,(31,58,13)),
 ("raspberry-pi-pico","microcontroller_board","Raspberry Pi","Pico","assumption",(1.8,5.5),300,(51,21,4)),
 ("esp32-wroom-32e","microcontroller_board","Espressif","ESP32-WROOM-32E","espressif",(3.0,3.6),240,(18,25.5,3.1)),
 ("arduino-uno-r4","microcontroller_board","Arduino","UNO R4 Minima","arduino",(6,24),200,(68.85,53.34,15)),
 ("bme280-breakout","environmental_sensor","Bosch","BME280","bosch",(1.71,3.6),1.0,(10,10,3)),
 ("bme280-i2c-module","temperature_sensor","Bosch","BME280 module","bosch",(3.0,5.0),1.0,(15,12,3)),
 ("ds18b20-module","temperature_sensor","Analog Devices","DS18B20","analog-ds18b20",(3.0,5.5),1.5,(5.2,4.2,4.8)),
 ("dht11-module","temperature_sensor","Curated","DHT11 module","assumption",(3.0,5.5),2.5,(28,15,8)),
 ("dht22-module","temperature_sensor","Curated","DHT22 module","assumption",(3.0,5.5),2.5,(28,15,10)),
 ("lm35-module","temperature_sensor","Curated","LM35 module","assumption",(4.0,30),1.0,(20,15,6)),
 ("aht20-module","temperature_sensor","Adafruit","AHT20 breakout","adafruit",(2.7,5.5),1.0,(25.5,17.8,4.6)),
 ("vl53l0x-module","distance_sensor","STMicroelectronics","VL53L0X","stmicro-vl53",(2.6,3.5),20,(4.4,2.4,1)),
 ("hc-sr04-class","distance_sensor","Curated","HC-SR04 class","assumption",(4.5,5.5),15,(45,20,15)),
 ("capacitive-soil-v1","soil_moisture_sensor","DFRobot","SEN0193","dfrobot",(3.3,5.5),5,(98,23,4)),
 ("photoresistor-module","light_sensor","Curated","CdS module","assumption",(3.0,5.0),5,(32,14,7)),
 ("bh1750-module","light_sensor","Curated","BH1750 module","assumption",(3.0,5.0),1,(18,13,4)),
 ("pir-hc-sr501","motion_sensor","Curated","HC-SR501 PIR","assumption",(4.5,12),65,(32,24,24)),
 ("mpu6050-module","orientation_sensor","Curated","MPU6050 module","assumption",(3.0,5.0),4,(21,16,4)),
 ("micro-pump-5v","small_dc_pump","Curated","5 V micro pump","assumption",(4.5,5.5),800,(60,40,35)),
 ("micro-pump-12v","small_dc_pump","Curated","12 V micro pump","assumption",(9,12),500,(60,40,35)),
 ("dc-fan-5v","fan","Curated","5 V brushless fan","assumption",(4.5,5.5),300,(40,40,10)),
 ("dc-fan-12v","fan","Curated","12 V brushless fan","assumption",(10.8,13.2),250,(60,60,15)),
 ("dc-motor-6v","small_dc_motor","Curated","DC toy motor","assumption",(3,6),500,(25,20,15)),
 ("sg90-servo","servo","Curated","SG90 class","assumption",(4.8,6),650,(23,12,29)),
 ("mg996r-servo","servo","Curated","MG996R class","assumption",(4.8,7.2),2500,(41,20,43)),
 ("drv8833-module","motor_driver","Texas Instruments","DRV8833 module","ti",(2.7,10.8),1500,(25,20,5)),
 ("tb6612-module","motor_driver","Toshiba","TB6612FNG module","adafruit",(2.7,5.5),1200,(25,20,5)),
 ("l298n-module","motor_driver","ST-compatible","L298N module","assumption",(5,35),2000,(44,44,28)),
 ("uln2003-module","motor_driver","Texas Instruments-compatible","ULN2003 module","assumption",(3,5.5),500,(32,24,8)),
 ("logic-mosfet-module","mosfet_driver","Curated","Logic MOSFET module","assumption",(3.3,5),10000,(34,26,12)),
 ("relay-module-5v","relay_module","Curated","5 V relay module","assumption",(4.5,5.5),80,(50,26,18)),
 ("bare-relay-5v","relay_module","Curated","5 V bare relay","assumption",(4.5,5.5),80,(20,15,15)),
 ("npn-switch","mosfet_driver","Curated","NPN transistor switch","assumption",(3.0,12),500,(10,5,10)),
 ("1n4007-diode","flyback_diode","STMicroelectronics","1N4007","st",(0,1000),1000,(10,3,3)),
 ("ss14-diode","flyback_diode","STMicroelectronics","SS14","st",(0,40),1000,(5,3,2)),
 ("resistor-220r","resistor","IEC family","220 ohm resistor","st",(0,250),0.25,(6.5,2.5,2.5)),
 ("resistor-1k","resistor","IEC family","1 kohm resistor","st",(0,250),0.25,(6.5,2.5,2.5)),
 ("resistor-10k","resistor","IEC family","10 kohm resistor","st",(0,250),0.25,(6.5,2.5,2.5)),
 ("resistor-4k7","resistor","IEC family","4.7 kohm resistor","st",(0,250),0.25,(6.5,2.5,2.5)),
 ("capacitor-generic","capacitor","IEC family","Generic capacitor","assumption",(0,50),1,(6,6,10)),
 ("led-generic","indicator","IEC family","Low-current LED","assumption",(1.8,3.3),20,(5,5,8)),
 ("push-button","switch","IEC family","Momentary push button","assumption",(0,24),100,(12,12,8)),
 ("terminal-block-2p","terminal_block","Curated","Two-position terminal block","assumption",(0,50),10000,(10,8,10)),
 ("supply-usb-5v-1a","low_voltage_power_source","Curated","5 V 1 A supply","assumption",(4.75,5.25),1000,(45,35,25)),
 ("supply-usb-5v-2a","low_voltage_power_source","Curated","5 V 2 A supply","assumption",(4.75,5.25),2000,(45,35,25)),
 ("supply-dc-12v-2a","low_voltage_power_source","Curated","12 V 2 A supply","assumption",(11.4,12.6),2000,(80,45,30)),
 ("buck-5v-3a","buck_converter","Texas Instruments","5 V buck module","ti",(7,24),3000,(43,21,14)),
 ("battery-aa4","battery","Curated","4xAA holder","assumption",(4,6.4),2000,(58,32,16)),
 ("enclosure-100x120","enclosure","Curated","Splash-resistant 100x120","assumption",(0,1),0,(100,120,60)),
 ("enclosure-160x200","enclosure","Curated","Splash-resistant 160x200","assumption",(0,1),0,(160,200,80)),
 # Voltage ranges for modules (ssd1306, lcd1602) include the board's regulator, not the bare chip's.
 ("ssd1306-oled-128x64","oled_display","Solomon Systech","SSD1306 0.96in OLED 128x64 (I2C)","solomon-ssd1306",(3.0,5.0),20,(27,27,4)),
 ("lcd1602-i2c","character_display","NXP","LCD1602 with PCF8574 I2C backpack","nxp-pcf8574",(4.5,5.5),30,(80,36,20)),
 ("max7219-matrix","led_matrix","Analog Devices","MAX7219 8x8 LED matrix (SPI)","analog-max7219",(4.0,5.5),330,(32,32,15)),
 ("ws2812b-stick-8","addressable_led","Worldsemi","WS2812B 8-LED stick","worldsemi-ws2812b",(3.5,5.3),480,(51,10,3)),
 ("rfm95w-lora","lora_module","HOPERF","RFM95W LoRa","hoperf-rfm95w",(1.8,3.7),120,(16,16,2)),
 ("nrf24l01-plus","rf_module","Nordic Semiconductor","nRF24L01+","nordic-nrf24",(1.9,3.6),14,(29,15,4)),
 ("neo6m-gps","gps_module","u-blox","NEO-6M GPS","ublox-neo6",(2.7,3.6),67,(25,35,8)),
 ("mfrc522-rfid","rfid_module","NXP","MFRC522 RFID reader","nxp-mfrc522",(2.5,3.6),100,(60,40,5)),
 ("ams1117-3v3","ldo_regulator","Advanced Monolithic Systems","AMS1117-3.3","ams-ams1117",(4.5,15),800,(10,7,2)),
 ("tp4056-charger","battery_charger","NanJing Top Power","TP4056 Li-ion charger","topower-tp4056",(4.0,8.0),1000,(26,17,4)),
 ("pot-10k","potentiometer","Bourns","PTV09 10 kohm potentiometer","bourns-ptv09",(0,5.5),1,(9.5,10,6)),
 ("buzzer-active-5v","buzzer","PUI Audio","AI-1223-TWT-5V-R active buzzer","pui-ai1223",(3.5,5.5),30,(12,12,9.5)),
)

# Single-unit list prices with their source and retrieval date; parts without an exact listing stay unpriced.
_PRICES = {
    "esp32-devkit-v1": (15.02, "https://futureelectronics.com/p/semiconductors--wireless-rf--rf-wireless/esp32-devkitc-32e-espressif-systems-3165275"),
    "ds18b20-module": (3.95, "https://www.adafruit.com/product/374"),
    "resistor-4k7": (0.10, "https://www.digikey.com/en/products/detail/stackpole-electronics-inc/CFM14JT4K70/2617764"),
    "1n4007-diode": (0.20, "https://azcus.digikey.com/en/products/detail/mcc-micro-commercial-components/1N4007-AP/10709094"),
    "supply-usb-5v-1a": (5.95, "https://www.adafruit.com/product/501"),
}

# Mechanical base only: no electrical rating is claimed, and the size is the common 830-point nominal, not a measured part.
_BREADBOARD = ComponentDefinition("breadboard-830", "breadboard", "Generic", "830-point solderless breadboard",
                                  {"dimensions": _p([165.1, 54.6, 8.5], "mm", "assumption", "nominal standard size")}, (),
                                  (_SOURCES["assumption"].evidence_id,), {"type": "proxy", "dimensionsProperty": "dimensions"})
_BREADBOARD_400 = ComponentDefinition("breadboard-400", "breadboard", "BusBoard", "BB400 400-point solderless breadboard",
                                      {"dimensions": _p([82, 55, 9], "mm", "busboard-bb400", "nominal standard size")}, (),
                                      (_SOURCES["busboard-bb400"].evidence_id,), {"type": "proxy", "dimensionsProperty": "dimensions"})
# Facts that are not a supply range or current: logic levels the electrical checks compare against the controller.
_EXTRA_PROPERTIES = {
    "pir-hc-sr501": {"logic_voltage": _p(3.3, "V", "assumption", "typical")},  # HC-SR501 output is 3.3 V
    "lcd1602-i2c": {"logic_voltage": _p(5.0, "V", "nxp-pcf8574", "typical")},
}


def _finish(item: ComponentDefinition) -> ComponentDefinition:
    """Attach category, pins, settings and support level; boards other than the DevKit are listed only."""
    identifier, category = item.component_definition_id, CATEGORY_BY_FAMILY[item.family]
    if identifier in _PRICES:
        item = replace(item, price={"usd": _PRICES[identifier][0], "source": _PRICES[identifier][1], "retrieved": "2026-10-27"})
    return replace(item, properties={**item.properties, **_EXTRA_PROPERTIES.get(identifier, {})}, category=category,
                   pins=pins_for_definition(identifier, item.family), settings=PART_SETTINGS.get(identifier, {}),
                   support="listed" if category == "boards" and identifier != "esp32-devkit-v1" else "full")


CATALOGUE = tuple(_finish(item) for item in (*(_definition(*spec) for spec in _SPECS), _BREADBOARD, _BREADBOARD_400))
BY_ID = {item.component_definition_id: item for item in CATALOGUE}


def evidence_records() -> tuple[EvidenceRecord, ...]: return tuple(_SOURCES.values())
def get(component_definition_id: str) -> ComponentDefinition:
    try: return BY_ID[component_definition_id]
    except KeyError as exc: raise KeyError(f"Unknown curated component: {component_definition_id}") from exc
def search(*, family: str | None = None, voltage: float | None = None, voltage_unit: str = "V",
           minimum_current_ma: float | None = None, interface: str | None = None) -> list[ComponentDefinition]:
    result=[]
    for item in CATALOGUE:
        if family and item.family != family: continue
        vr=item.properties.get("supply_voltage_range")
        if voltage is not None and (not vr or not in_range(voltage,voltage_unit,*vr.value,vr.unit or "V")): continue
        current=item.properties.get("current")
        if minimum_current_ma is not None and (not current or float(current.value)<minimum_current_ma): continue
        if interface and interface not in item.interfaces: continue
        result.append(item)
    return result
