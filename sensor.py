"""Sensor platform for integration_blueprint."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CURRENCY_EURO, ENERGY_KILO_WATT_HOUR, ENERGY_MEGA_WATT_HOUR
from homeassistant.util import dt
from dataclasses import dataclass
from statistics import mean
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
from .const import PEAKHOURS, OFFPEAKHOURS1, OFFPEAKHOURS2
import logging

_LOGGER = logging.getLogger(__name__)



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
        #return f"{self._platform_name} {self.entity_description.name}"
        return f"{self.entity_description.name}"

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._platform_name}_{self.entity_description.key}"  


    def _calc_price(self, price):
        res = price
        if self.entity_description.extra: res = res + self.entity_description.extra
        if self.entity_description.minus: res = res - self.entity_description.minus
        if self.entity_description.scale: res = res * self.entity_description.scale 
        return res


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
            rec = None
            if self.coordinator.data: 
                try:  rec = self.coordinator.data[self.entity_description.source].get((nowday, nowhour, 0,) , None)
                except:
                    if self.coordinator.data[self.entity_description.source] != None: _LOGGER.error(f"cannot find {(searchday, searchhour), } data for {self.entity_description.source} : {self.coordinator.data}")
            #_LOGGER.error(f"no error - day = {searchday} hour = {searchhour} price = {rec}")
            if rec: return self._calc_price( rec["price"] )
            else:   return None

    
    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.entity_description.with_attribs:
            localday = datetime.now().day
            localtomorrow = (datetime.now() + timedelta(days=1)).day
            if self.coordinator.data[self.entity_description.source]:
                thismin = 9999
                thismax = -9999
                today = []
                tomorrow = []
                raw_today = []
                raw_tomorrow = []
                peak = []
                off_peak_1 = []
                off_peak_2 = []
                for (day, hour, minute,), value in self.coordinator.data[self.entity_description.source].items():
                    price = self._calc_price(value["price"])
                    if price < thismin: thismin = price
                    if price > thismax: thismax = price
                    zulutime = value["zulutime"]
                    localtime = dt.as_local( value["localtime"] )
                    interval = value["interval"]
                    if localtime.day == localday:
                        today.append(price)
                        if localtime.hour in PEAKHOURS: peak.append(price)
                        if localtime.hour in OFFPEAKHOURS1: off_peak_1.append(price)
                        if localtime.hour in OFFPEAKHOURS2: off_peak_2.append(price)
                        raw_today.append( {"start": localtime, "end": localtime + timedelta(seconds=interval) , "value": price } )
                    elif localtime.day == localtomorrow:
                        tomorrow.append(price)
                        raw_tomorrow.append( {"start": localtime, "end": localtime + timedelta(seconds=interval) , "value": price} )
                self._attrs = { 
                    'current_price': self.native_value,
                    'average': mean(today),
                    'off_peak_1': mean(off_peak_1) if off_peak_1 else 0,
                    'off_peak_2': mean(off_peak_2) if off_peak_2 else 0,
                    'peak': mean(peak) if mean else 0,
                    'min': thismin,
                    'max': thismax,
                    'unit':  {ENERGY_KILO_WATT_HOUR},
                    'currency' : CURRENCY_EURO,
                    'country': None,
                    'region': 'BE',
                    'low_price': False,
                    'tomorrow_valid': True,
                    'today': today,
                    'tomorrow': tomorrow,
                    'raw_today': raw_today,
                    'raw_tomorrow': raw_tomorrow,
                }
                return self._attrs

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
            with_attribs = True,
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
            with_attribs = True,
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

    _LOGGER.info(f"coordinator data in setup entry: {coordinator.data}")   
    async_add_entities(entities)




