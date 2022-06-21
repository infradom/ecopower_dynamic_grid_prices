"""Sensor platform for integration_blueprint."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
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
            searchhour = self.entity_description.key.partition("_slot_")[2] # empty if current price
            if searchhour: searchhour = int(searchhour)
            if   "today"    in self.entity_description.key: searchday = nowday
            elif "tomorrow" in self.entity_description.key: searchday = nextday
            else: 
                searchday = nowday
                searchhour = nowhour
            if self.coordinator.data: rec = self.coordinator.data.get((searchday, searchhour, 0,) , None)
            else: rec = None
            #_LOGGER.error(f"no error - day = {searchday} hour = {searchhour} price = {rec}")
            if rec:
                res = rec["price"]
                if self.entity_description.extra: res = res + self.entity_description.extra
                if self.entity_description.minus: res = res - self.entity_description.minus
                if self.entity_description.scale: res = res * self.entity_description.scale
                return res
            else: return None

    #@property
    #def icon(self):
    #    """Return the icon of the sensor."""
    #    return ICON


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    entities = []
    coordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.info(f"no error - device entry content {dir(entry)} entry_id: {entry.entry_id} data: {entry.data} options: {entry.options} state: {entry.state} source: {entry.source}")
    device_info = { "identifiers": {(DOMAIN,)},   "name" : NAME, }
    # entry.data is a dict that the config flow attributes
    descr = DynPriceSensorDescription( 
            name="Current Price Entsoe",
            key="current_price_entsoe",
            native_unit_of_measurement="EUR",
            device_class = DEVICE_CLASS_MONETARY,
    )
    device = DynPriceSensor(coordinator, device_info, descr)
    entities.append(device)

    descr = DynPriceSensorDescription( 
            name="Current Price Injection",
            key="current_price_injection",
            native_unit_of_measurement="EUR",
            device_class = DEVICE_CLASS_MONETARY,
            scale=entry.data["entsoe_factor_C"],
            minus=entry.data["entsoe_factor_D"],
    )
    sensor = DynPriceSensor(coordinator, device_info, descr)
    entities.append(sensor)

    descr = DynPriceSensorDescription( 
            name="Current Price Consumption",
            key="current_price_consumption",
            native_unit_of_measurement="EUR",
            device_class = DEVICE_CLASS_MONETARY,
            scale=entry.data["entsoe_factor_A"],
            extra=entry.data["entsoe_factor_B"],
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
            native_unit_of_measurement="EUR",
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
            native_unit_of_measurement="EUR",
            device_class = DEVICE_CLASS_MONETARY,
            static_value = entry.data["entsoe_factor_D"],
    )
    sensor = DynPriceSensor(coordinator, device_info, descr)
    entities.append(sensor)

    for i in range(0,24):
        descr = DynPriceSensorDescription( 
            name=f"Entsoe Price Today Slot {i:02}",
            key=f"entsoe_price_today_slot_{i:02}",
            native_unit_of_measurement="EUR",
            device_class = DEVICE_CLASS_MONETARY,
            )
        sensor =  DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)

    _LOGGER.info(f"no error - coordinator data in setup entry: {coordinator.data}")   
    async_add_entities(entities)




