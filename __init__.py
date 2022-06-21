"""The DynGridPricesSolar integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import async_timeout
import aiohttp, asyncio
import xmltodict
import json
import logging
from datetime import datetime, timezone, timedelta
import time
from collections.abc import Mapping
from .const import ENTSOE_DAYAHEAD_URL, ECOPWR_DAYAHEAD_URL, ENTSOE_HEADERS, ECOPWR_HEADERS, STARTUP_MESSAGE, CONF_ENTSOE_AREA, CONF_ENTSOE_TOKEN
from .const import DOMAIN, PLATFORMS, SENSOR

# TODO List the platforms that you want to support.

SCAN_INTERVAL = timedelta(seconds=900)
TIMEOUT = 10

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

    token = entry.data.get(CONF_ENTSOE_TOKEN)
    area = entry.data.get(CONF_ENTSOE_AREA)

    session = async_get_clientsession(hass)
    client = EntsoeApiClient(token, area, session)

    coordinator = EntsoeDataUpdateCoordinator(hass, client=client)
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


class EntsoeApiClient:
    def __init__(self, token: str, area: str, session: aiohttp.ClientSession) -> None:
        self._token = token
        self._area = area
        self._session = session

    async def async_get_data(self) -> dict:
        now = datetime.now(timezone.utc)
        start = (now + timedelta(days=0)).strftime("%Y%m%d0000") #"202206152200"
        end   = (now + timedelta(days=1) ).strftime("%Y%m%d0000") #"202206202200"
        _LOGGER.info(f"no error: entsoe interval {start} {end}")
        url = ENTSOE_DAYAHEAD_URL.format(TOKEN = self._token, AREA = self._area, START = start, END = end)
        try:
            async with async_timeout.timeout(TIMEOUT):
                response = await self._session.get(url, headers=ENTSOE_HEADERS)
                if response.status != 200:
                    _LOGGER.error('invalid response code from entsoe: {response.status}')
                    return None
                xml = await response.text()
                xpars = xmltodict.parse(xml)
                xpars = xpars['Publication_MarketDocument']
                #jsond = json.dumps(xpars, indent=2)
                #_LOGGER.info(jsond)
                series = xpars['TimeSeries']
                if isinstance(series, Mapping): series = [series]
                res = { 'lastday' : 0, 'points': {} }
                #res = {}
                for ts in series:
                    start = ts['Period']['timeInterval']['start']
                    startts = datetime.strptime(start,'%Y-%m-%dT%H:%MZ').replace(tzinfo=timezone.utc).timestamp()
                    end = ts['Period']['timeInterval']['end']
                    if ts['Period']['resolution'] == 'PT60M': seconds = 3600
                    else: seconds = None
                    for point in ts['Period']['Point']:
                        offset = seconds * (int(point['position'])-1)
                        timestamp = startts + offset
                        zulutime  = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                        localtime = datetime.fromtimestamp(timestamp)
                        price = float(point['price.amount'])
                        _LOGGER.info(f"{(zulutime.day, zulutime.hour, zulutime.minute,)} zulutime={datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()}Z localtime={datetime.fromtimestamp(timestamp).isoformat()} price={price}" )
                        res['points'][(zulutime.day, zulutime.hour, zulutime.minute,)] = {"price": price, "zulutime": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(), "localtime": datetime.fromtimestamp(timestamp).isoformat()}
                        #res['points'][(zulutime.day, zulutime.hour, zulutime.minute,)] = {"price": price, "zulutime": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(), "localtime": datetime.fromtimestamp(timestamp).isoformat()}
                        if zulutime.day > res['lastday']: res['lastday'] = zulutime.day
                _LOGGER.info(f"fetched from entsoe: {res}")
                return res             
        except Exception as exception:
            _LOGGER.exception(f"cannot fetch api data: {exception}") 


class EntsoeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(  self, hass: HomeAssistant, client: EntsoeApiClient) -> None:
        """Initialize."""
        self.api = client
        self.platforms = []
        self.lastfetch = 0
        self.cache = None

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        now = time.time()
        zulutime = time.gmtime(now)
        _LOGGER.info(f"checking if api update is needed or data can be retrieved from cache at zulutime: {zulutime}")
        # reduce number of cloud fetches
        if not self.cache or ((now - self.lastfetch >= 3600) and (zulutime.tm_hour >= 12) and (self.cache['lastday'] <= zulutime.tm_mday)):
            try:
                res = await self.api.async_get_data()
                self.lastfetch = now
                self.cache = res
            except Exception as exception:
                raise UpdateFailed() from exception
        return self.cache['points']


