"""The DynGridPricesSolar integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, CURRENCY_EURO

import async_timeout
import aiohttp, asyncio
import logging
import datetime
import pandas
from .const import STARTUP_MESSAGE, CONF_ECOPWR_TOKEN, CONF_TEST_API
from .const import ECOPWR_HEADERS, ECOPWR_DAYAHEAD_URL, ECOPWR_DAYAHEAD_URL_ACC
from .const import DOMAIN, PLATFORMS, SENSOR
from .const import CONF_ECOPWR_API_C, CONF_ECOPWR_API_I

# TODO List the platforms that you want to support.

SCAN_INTERVAL = datetime.timedelta(minutes=1) #TODO 

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DynGridPrices from a config entry."""
    # TODO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    ecopwr_token = entry.data.get(CONF_ECOPWR_TOKEN)
    curve_c = entry.data.get(CONF_ECOPWR_API_C)
    curve_i = entry.data.get(CONF_ECOPWR_API_I)
    test_api = entry.data.get(CONF_TEST_API)
    ecopower_session = async_get_clientsession(hass)
    ecopower_client = EcopowerApiClient(ecopower_session, ecopwr_token, curve_c, curve_i, test_api)

    coordinator = DynPriceUpdateCoordinator(hass, ecopower_client = ecopower_client)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class EcopowerApiClient:
    def __init__(
        self, session: aiohttp.ClientSession, token: str, curve_c, curve_i , test_api
    ) -> None:
        self._token = token
        self._session = session
        self._test_api = test_api
        self._url_c = ECOPWR_DAYAHEAD_URL.format(CURVE=curve_c)
        self._url_i = ECOPWR_DAYAHEAD_URL.format(CURVE=curve_i)
        if self._test_api:
            self._url_c = ECOPWR_DAYAHEAD_URL_ACC.format(CURVE=curve_c)
            self._url_i = ECOPWR_DAYAHEAD_URL_ACC.format(CURVE=curve_i)
        # _LOGGER.debug(f"urls: {self._url_c}, {self.url_i}")

    async def async_get_data(self, url) -> dict:
        try:
            async with async_timeout.timeout(8):
                headers = ECOPWR_HEADERS
                headers["authorization"] = f"Bearer {self._token}"
                response = await self._session.get(url, headers=headers)
                response.raise_for_status()
                data = await response.json()
                df = pandas.DataFrame.from_records(data["values"], index="date")
                df.index = pandas.to_datetime(df.index).tz_convert(tz="Europe/Brussels") 
                df["value"] = df["value"] * 10**-3  # MWh -> KWh
                # #df.round("H") df = df.drop_duplicates()
                # df = df.groupby(pandas.Grouper(freq='60Min')).mean()
                return df
        except asyncio.CancelledError:
            _LOGGER.exception(f"cancelled error received during {url} fetch")
            # cleanup
            raise     
        except Exception as exception:
            _LOGGER.exception(f"cannot fetch api data from ecopower: {exception}") 


class DynPriceUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(  self, hass: HomeAssistant, ecopower_client: EcopowerApiClient) -> None:
        """Initialize."""
        self.platforms = []
        self.ecopowerapi = ecopower_client
        self.hass = hass
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""

        df_c = await self.ecopowerapi.async_get_data(url = self.ecopowerapi._url_c )
        _LOGGER.info("fetched ecopower consumption url")
        df_i = await self.ecopowerapi.async_get_data(url = self.ecopowerapi._url_i )
        _LOGGER.info("fetched ecopower injection url")
        await self._insert_statistics(df_c,'ecopower_consumption_price')
        await self._insert_statistics(df_i,'ecopower_injection_price')

        return {'ecopower_consumption_price':df_c,
                'ecopower_injection_price': df_i}



    async def _insert_statistics(self, df, name):
        """Insert historical statistics ."""
        aggs = {f"{ag}_value": ('value', ag) for ag in ['min', 'mean', 'max']}
        df_hour = df.groupby(pandas.Grouper(freq='60Min')).agg(**aggs)

        statistic_id = f"{DOMAIN}:{name}".lower() #external statistic
        # statistic_id = f"sensor.{column}".lower()

        _LOGGER.info(f"adding historical statistics for {statistic_id}")

        statistics = []
        for dt, mean, min, max in zip(df_hour.index, df_hour[f"mean_value"], df_hour[f"min_value"], df_hour[f"max_value"]):
            statistics.append(
                StatisticData(
                    start=dt,
                    mean=mean, 
                    min=min, 
                    max=max, 
                ))

        metadata = StatisticMetaData(
            has_mean=True,
            has_sum=False,
            name=name,
            source=DOMAIN,
            # source='recorder',
            statistic_id=statistic_id,
            unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}", #
        )
        _LOGGER.info(f"adding {len(statistics)} statistics for {statistic_id}")
        async_add_external_statistics(self.hass, metadata, statistics)
        # async_import_statistics(hass, metadata, statistics)



