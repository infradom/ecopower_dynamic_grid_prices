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
    dummy: int = None


class DynPriceSensor(DynPriceEntity, SensorEntity):
    """Sensor class."""
    def __init__(self, coordinator, device_info, description: DynPriceSensorDescription):
        DynPriceEntity.__init__(self, coordinator)
        #self._id = id
        self.entity_description: DynPriceSensorDescription = description
        self._attr_device_info = device_info
        self._platform_name = 'sensor'

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
        _LOGGER.error(f"no error - coordinator data in sensor native value: {self.coordinator.data}")
        return self.coordinator.data.get(self.entity_description.key)

    #@property
    #def icon(self):
    #    """Return the icon of the sensor."""
    #    return ICON


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    entities = []
    coordinator = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.error(f"no error - device entry content {dir(entry)} entry_id: {entry.entry_id} data: {entry.data} options: {entry.options} state: {entry.state} source: {entry.source}")
    # entry.data is a dict that the config flow attributes
    descr = DynPriceSensorDescription( 
            name=f"Entsoe Current Price",
            key=f"entsoe_current_price",
            native_unit_of_measurement="EUR",
            device_class = DEVICE_CLASS_MONETARY,
    )
    device_info = { "identifiers": {(DOMAIN,)},   "name" : NAME, }
    device = DynPriceSensor(coordinator, device_info, descr)

    entities.append(device)

    for i in range(0,24):
        descr = DynPriceSensorDescription( 
            name=f"Entsoe Price Today Slot {i:02}",
            key=f"entsoe_price_today_slot_{i:02}",
            native_unit_of_measurement="EUR",
            device_class = DEVICE_CLASS_MONETARY,
            )
        sensor =  DynPriceSensor(coordinator, device_info, descr)
        entities.append(sensor)
    # create other entities
    _LOGGER.error(f"no error - coordinator data in setup entry: {coordinator.data}")   
    async_add_entities(entities)




