"""Sensor platform for integration_blueprint."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import ENERGY_KILO_WATT_HOUR, CURRENCY_EURO
from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorEntity, 
    SensorStateClass
)
from homeassistant.const import (DEVICE_CLASS_MONETARY,)
from .const import NAME, VERSION, ATTRIBUTION
from .const import DEFAULT_NAME, DOMAIN, ICON, SENSOR
import logging


_LOGGER = logging.getLogger(__name__)


class DynPriceSensor(CoordinatorEntity, SensorEntity):
    """Sensor class."""
    def __init__(self, coordinator, description: SensorEntityDescription):
        CoordinatorEntity.__init__(self, coordinator)
        #self._id = id
        self.entity_description: SensorEntityDescription = description

    @property
    def native_value(self):
        return self.coordinator.data[self.entity_description.key]
        # current_hour=pandas.Timestamp.now(tz="Europe/Brussels").floor("H")
        # return self.coordinator.data[self.entity_description.key].loc[current_hour,'value']


async def async_setup_entry(hass, entry, async_add_entities):
    """Setup sensor platform."""
    entities = []
    coordinator = hass.data[DOMAIN][entry.entry_id]
    # entry.data is a dict that the config flow attributes

    descr = SensorEntityDescription( 
        name="Ecopower Consumption Price",
        key="ecopower_consumption_price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        device_class = DEVICE_CLASS_MONETARY,
        # as we collect our own statistics, we don't want state_class to be set
        # state_class = SensorStateClass.MEASUREMENT, 
    )
    sensor = DynPriceSensor(coordinator, descr)
    entities.append(sensor)

    descr = SensorEntityDescription( 
        name="Ecopower Injection Price",
        key="ecopower_injection_price",
        native_unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",
        device_class = DEVICE_CLASS_MONETARY,
        # as we collect our own statistics, we don't want state_class to be set
        # state_class = SensorStateClass.MEASUREMENT,
    )
    sensor = DynPriceSensor(coordinator, descr)
    entities.append(sensor)

    # pos value meaning high price relative to the rest of the hours
    # neg value meaning low price relative to the rest of the hours
    descr = SensorEntityDescription( 
        name="Ecopower Price Z-Score",
        key="ecopower_zscore",
        native_unit_of_measurement="",
        device_class = DEVICE_CLASS_MONETARY,
        # state_class = SensorStateClass.MEASUREMENT,
    )
    sensor = DynPriceSensor(coordinator, descr)
    entities.append(sensor)

    #_LOGGER.info(f"coordinator data in setup entry: {coordinator.data}")   
    async_add_entities(entities)




