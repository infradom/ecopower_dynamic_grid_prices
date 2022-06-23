"""Sensor platform for integration_blueprint."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CURRENCY_EURO, ENERGY_KILO_WATT_HOUR, ENERGY_MEGA_WATT_HOUR
from dataclasses import dataclass
from homeassistant.components.sensor import (
    SensorEntityDescription,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from homeassistant.const import (DEVICE_CLASS_MONETARY,)
from .const import NAME, VERSION, ATTRIBUTION
from .const import DEFAULT_NAME, DOMAIN, ICON, SENSOR
from .const import CONF_ENTSOE_TOKEN, CONF_ECOPWR_TOKEN
import logging

_LOGGER = logging.getLogger(__name__)

_PRICE_SENSOR_ATTRIBUTES_MAP = { # borrowed/stolen from PVPC integration ;-)
    "tariff": "tariff",
    "period": "period",
    "available_power": "available_power",
    "next_period": "next_period",
    "hours_to_next_period": "hours_to_next_period",
    "next_better_price": "next_better_price",
    "hours_to_better_price": "hours_to_better_price",
    "num_better_prices_ahead": "num_better_prices_ahead",
    "price_position": "price_position",
    "price_ratio": "price_ratio",
    "max_price": "max_price",
    "max_price_at": "max_price_at",
    "min_price": "min_price",
    "min_price_at": "min_price_at",
    "next_best_at": "next_best_at",
    "price_00h": "price_00h",
    "price_01h": "price_01h",
    "price_02h": "price_02h",
    "price_02h_d": "price_02h_d",  # only on DST day change with 25h
    "price_03h": "price_03h",
    "price_04h": "price_04h",
    "price_05h": "price_05h",
    "price_06h": "price_06h",
    "price_07h": "price_07h",
    "price_08h": "price_08h",
    "price_09h": "price_09h",
    "price_10h": "price_10h",
    "price_11h": "price_11h",
    "price_12h": "price_12h",
    "price_13h": "price_13h",
    "price_14h": "price_14h",
    "price_15h": "price_15h",
    "price_16h": "price_16h",
    "price_17h": "price_17h",
    "price_18h": "price_18h",
    "price_19h": "price_19h",
    "price_20h": "price_20h",
    "price_21h": "price_21h",
    "price_22h": "price_22h",
    "price_23h": "price_23h",
    # only seen in the evening
    "next_better_price (next day)": "next_better_price (next day)",
    "hours_to_better_price (next day)": "hours_to_better_price (next day)",
    "num_better_prices_ahead (next day)": "num_better_prices_ahead (next day)",
    "price_position (next day)": "price_position (next day)",
    "price_ratio (next day)": "price_ratio (next day)",
    "max_price (next day)": "max_price (next day)",
    "max_price_at (next day)": "max_price_at (next day)",
    "min_price (next day)": "min_price (next day)",
    "min_price_at (next day)": "min_price_at (next day)",
    "next_best_at (next day)": "next_best_at (next day)",
    "price_next_day_00h": "price_next_day_00h",
    "price_next_day_01h": "price_next_day_01h",
    "price_next_day_02h": "price_next_day_02h",
    "price_next_day_02h_d": "price_next_day_02h_d",
    "price_next_day_03h": "price_next_day_03h",
    "price_next_day_04h": "price_next_day_04h",
    "price_next_day_05h": "price_next_day_05h",
    "price_next_day_06h": "price_next_day_06h",
    "price_next_day_07h": "price_next_day_07h",
    "price_next_day_08h": "price_next_day_08h",
    "price_next_day_09h": "price_next_day_09h",
    "price_next_day_10h": "price_next_day_10h",
    "price_next_day_11h": "price_next_day_11h",
    "price_next_day_12h": "price_next_day_12h",
    "price_next_day_13h": "price_next_day_13h",
    "price_next_day_14h": "price_next_day_14h",
    "price_next_day_15h": "price_next_day_15h",
    "price_next_day_16h": "price_next_day_16h",
    "price_next_day_17h": "price_next_day_17h",
    "price_next_day_18h": "price_next_day_18h",
    "price_next_day_19h": "price_next_day_19h",
    "price_next_day_20h": "price_next_day_20h",
    "price_next_day_21h": "price_next_day_21h",
    "price_next_day_22h": "price_next_day_22h",
    "price_next_day_23h": "price_next_day_23h",
}



class DynPriceEntity(CoordinatorEntity):
    def __init__(self, coordinator): #, id):
        super().__init__(coordinator)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "attribution": ATTRIBUTION,
            "id": str(self.coordinator.data.get("id")),
            "integration": DOMAIN,
        }

@dataclass
class DynPriceSensorDescription(SensorEntityDescription):
    # add additional attributes if applicable
    scale: float = None    # scaling factor 
    extra: float = None    # scaling factor : result = scale * (value+extra)
    minus: float = None    # scaling factor : result = scale * (value-minus)
    static_value: float = None # fixed static value from config entry
    with_attribs: bool = False # add time series as attributes
    source: str = 'entsoe' # source of information: entsoe or ecopower



class DynPriceSensor(DynPriceEntity, SensorEntity):
    """Sensor class."""
    def __init__(self, coordinator, device_info, description: DynPriceSensorDescription):
        DynPriceEntity.__init__(self, coordinator)
        #self._id = id
        self.entity_description: DynPriceSensorDescription = description
        self._attr_device_info = device_info
        self._platform_name = 'sensor'
        """self._value = value # typically a static value from config entry
        self._scale = scale # scaling factor 
        self._extro = extra # extra cost"""

    @property
    def name(self):
        """Return the name."""
        return f"{self._platform_name} {self.entity_description.name}"

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._platform_name}_{self.entity_description.key}"  


    @property
    def native_value(self):
        """Return the native value of the sensor."""
        if self.entity_description.static_value: return self.entity_description.static_value # static config variable
        else:
            #_LOGGER.error(f"no error - coordinator data in sensor native value: {self.coordinator.data}")
            now = datetime.utcnow()
            nowday = now.day
            nextday = (now + timedelta(days=1)).day
            nowhour = now.hour
            #_LOGGER.error(f"no error =  nowhour {nowhour} nowday = {nowday}")
            #searchhour = self.entity_description.key.partition("_slot_")[2] # empty if current price
            #if searchhour: searchhour = int(searchhour)
            #if   "today"    in self.entity_description.key: searchday = nowday
            #elif "tomorrow" in self.entity_description.key: searchday = nextday
            #else: 
            #   searchday = nowday
            #   searchhour = nowhour

            #_LOGGER.info(f"native value: coordinator: {self.coordinator} data: {self.coordinator.data} source: {self.entity_description.source}")
            rec = None
            if self.coordinator.data: 
                try:  rec = self.coordinator.data[self.entity_description.source].get((nowday, nowhour, 0,) , None)
                except:
                    if self.coordinator.data[self.entity_description.source] != None: _LOGGER.error(f"cannot find {(searchday, searchhour), } data for {self.entity_description.source} : {self.coordinator.data}")
            #_LOGGER.error(f"no error - day = {searchday} hour = {searchhour} price = {rec}")
            if rec:
                res = rec["price"]
                if self.entity_description.extra: res = res + self.entity_description.extra
                if self.entity_description.minus: res = res - self.entity_description.minus
                if self.entity_description.scale: res = res * self.entity_description.scale
                return res
            else: return None

    
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.entity_description.with_attribs:
            self._attrs = {}
            localday = datetime.now().day
            localtomorrow = (datetime.now() + timedelta(days=1)).day
            if self.coordinator.data[self.entity_description.source]:
                for (day, hour, minute,), value in self.coordinator.data[self.entity_description.source].items():
                    price = value["price"]
                    zulutime = value["zulutime"]
                    localtime = value["localtime"]
                    if   localtime.day == localday: patt = f"price_{localtime.hour:02}h"
                    elif localtime.day == localtomorrow: patt = f"price_next_day_{localtime.hour:02}h"
                    else: patt = None
                    if patt: self._attrs[patt] = price
                return self._attrs
        else: return None    



async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    entities = []
    coordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info(f"no error - device entry content {dir(entry)} entry_id: {entry.entry_id} data: {entry.data} options: {entry.options} state: {entry.state} source: {entry.source}")
    device_info = { "identifiers": {(DOMAIN,)},   "name" : NAME, }
    # entry.data is a dict that the config flow attributes
    if entry.data[CONF_ENTSOE_TOKEN]:
        descr = DynPriceSensorDescription( 
            name="Entsoe Price",
            key="entsoe_price",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_MEGA_WATT_HOUR}",
            device_class = DEVICE_CLASS_MONETARY,
            with_attribs = True,
            source       = "entsoe",
        )
        sensor = DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)

        descr = DynPriceSensorDescription( 
            name="Computed Price Consumption",
            key="computed price_consumption",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
            device_class = DEVICE_CLASS_MONETARY,
            scale=entry.data["entsoe_factor_A"],
            extra=entry.data["entsoe_factor_B"],
        )
        sensor = DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)

        descr = DynPriceSensorDescription( 
            name="Computed Price Injection",
            key="computed_price_injection",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
            device_class = DEVICE_CLASS_MONETARY,
            scale=entry.data["entsoe_factor_C"],
            minus=entry.data["entsoe_factor_D"],
        )
        sensor = DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)

        descr = DynPriceSensorDescription( 
            name="Entsoe Factor A Consumption Scale",
            key="entsoe_factor_a_consumption_scale",
            static_value = entry.data['entsoe_factor_A'],
        )
        sensor = DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)

        descr = DynPriceSensorDescription( 
            name="Entsoe Factor B Consumption Extracost",
            key="entsoe_factor_b_consumption_extracost",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_MEGA_WATT_HOUR}",
            device_class = DEVICE_CLASS_MONETARY,
            static_value = entry.data["entsoe_factor_B"],
        )
        sensor = DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)

        descr = DynPriceSensorDescription( 
            name="Entsoe Factor C Production Scale",
            key="entsoe_factor_c_production_scale",
            static_value = entry.data["entsoe_factor_C"],
        )
        sensor = DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)

        descr = DynPriceSensorDescription( 
            name="Entsoe Factor D Production Extrafee",
            key="entsoe_factor_d_production_extrafee",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_MEGA_WATT_HOUR}",
            device_class = DEVICE_CLASS_MONETARY,
            static_value = entry.data["entsoe_factor_D"],
        )
        sensor = DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)

    if entry.data[CONF_ECOPWR_TOKEN]:
        descr = DynPriceSensorDescription( 
            name="Ecopower Consumption Price",
            key="ecopower_consumption_price",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
            device_class = DEVICE_CLASS_MONETARY,
            with_attribs = True,
            scale        = 0.001,
            source       = "ecopower_consumption",
        )
        sensor = DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)

        descr = DynPriceSensorDescription( 
            name="Ecopower Injection Price",
            key="ecopower_injection_price",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
            device_class = DEVICE_CLASS_MONETARY,
            with_attribs = True,
            scale        = 0.001,
            source       = "ecopower_injection",
        )
        sensor = DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)
    """
    for i in range(0,24):
        descr = DynPriceSensorDescription( 
            name=f"Entsoe Price Today Slot {i:02}",
            key=f"entsoe_price_today_slot_{i:02}",
            native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
            device_class = DEVICE_CLASS_MONETARY,
            )
        sensor =  DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)
    """
    _LOGGER.info(f"coordinator data in setup entry: {coordinator.data}")   
    async_add_entities(entities)




