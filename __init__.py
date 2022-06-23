"""The DynGridPricesSolar integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady
import async_timeout
import aiohttp, asyncio
import xmltodict
import json
import logging
from datetime import datetime, timezone, timedelta
import time
from collections.abc import Mapping
from .const import ENTSOE_DAYAHEAD_URL, ENTSOE_HEADERS,STARTUP_MESSAGE, CONF_ENTSOE_AREA, CONF_ENTSOE_TOKEN, CONF_ECOPWR_TOKEN
from .const import ECOPWR_CONSUMPTION, ECOPWR_INJECTION, ECOPWR_HEADERS, ECOPWR_DAYAHEAD_URL
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

    entsoe_client   = None
    ecopower_client = None
    entsoe_token = entry.data.get(CONF_ENTSOE_TOKEN)
    ecopwr_token = entry.data.get(CONF_ECOPWR_TOKEN)
    area = entry.data.get(CONF_ENTSOE_AREA)
    if entsoe_token != "None": # deliberately string None since paramter is required
        entsoe_session = async_get_clientsession(hass)
        entsoe_client = EntsoeApiClient(entsoe_session, entsoe_token, area)
    if ecopwr_token:
        ecopower_session = async_get_clientsession(hass)
        ecopower_client = EcopowerApiClient(ecopower_session, ecopwr_token)

    coordinator = DynPriceUpdateCoordinator(hass, entsoe_client= entsoe_client, ecopower_client = ecopower_client)
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
    def __init__(self, session: aiohttp.ClientSession, token: str, area: str) -> None:
        self._token   = token
        self._area    = area
        self._session = session

    async def async_get_data(self) -> dict:
        #today = datetime.now()               # exceptionally in localtime
        #tomorrow = today + timedelta(days=1) # exceptionally in localtime
        now = datetime.now(timezone.utc)
        start = (now + timedelta(days=0)).strftime("%Y%m%d0000") #"202206152200"
        end   = (now + timedelta(days=1) ).strftime("%Y%m%d0000") #"202206202200"
        url = ENTSOE_DAYAHEAD_URL.format(TOKEN = self._token, AREA = self._area, START = start, END = end)
        _LOGGER.info(f"entsoe interval {start} {end} fetchingurl = {url}")
        try:
            async with async_timeout.timeout(TIMEOUT):
                response = await self._session.get(url, headers=ENTSOE_HEADERS)
                if response.status != 200:
                    _LOGGER.error(f'invalid response code from entsoe: {response.status}')
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
                        #if   localtime.day == today.day:    patt = f"price_{localtime.hour:02}h"
                        #elif localtime.day == tomorrow.day: patt = f"price_next_day_{localtime.hour:02}h"
                        #else patt = None
                        #if patt: res['points'][patt] = {"price": price, "zulutime": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(), "localtime": datetime.fromtimestamp(timestamp).isoformat()}
                        res['points'][(zulutime.day, zulutime.hour, zulutime.minute,)] = {"price": price, "zulutime": datetime.fromtimestamp(timestamp, tz=timezone.utc), "localtime": datetime.fromtimestamp(timestamp)}
                        if zulutime.day > res['lastday']: res['lastday'] = zulutime.day
                _LOGGER.info(f"fetched from entsoe: {res}")
                return res             
        except Exception as exception:
            _LOGGER.exception(f"cannot fetch api data from entsoe: {exception}") 


class EcopowerApiClient:
    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self._token = token
        self._session = session

    async def async_get_data(self, url: str) -> dict:
        now = datetime.now(timezone.utc)
        try:
            async with async_timeout.timeout(TIMEOUT):
                headers = ECOPWR_HEADERS
                headers['authorization'] = headers['authorization'].format(TOKEN = self._token)
                response = await self._session.get(url, headers=headers)
                if response.status != 200:
                    _LOGGER.error(f'invalid response code from ecopower: {response.status}')
                    return None
                xpars = await response.json()
                res = { 'lastday' : 0, 'points': {} }
                idContainer = xpars['idContainer']
                if idContainer:
                    #jsond = json.dumps(xpars, indent=2)
                    #_LOGGER.info(jsond)
                    series = xpars['values']
                    seconds = 900
                    for point in series:
                        if point["valueStatus"] == "valid": price = float(point["value"])
                        zulutime = datetime.strptime(point["date"],'%Y-%m-%dT%H:%M:%S+00:00').replace(tzinfo=timezone.utc)
                        timestamp = zulutime.timestamp()
                        localtime = datetime.fromtimestamp(timestamp)
                        _LOGGER.info(f"{(zulutime.day, zulutime.hour, zulutime.minute,)} zulutime={datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()}Z localtime={datetime.fromtimestamp(timestamp).isoformat()} price={price}" )
                        res['points'][(zulutime.day, zulutime.hour, zulutime.minute,)] = {"price": price, "zulutime": datetime.fromtimestamp(timestamp, tz=timezone.utc), "localtime": datetime.fromtimestamp(timestamp)}
                        if zulutime.day > res['lastday']: res['lastday'] = zulutime.day
                _LOGGER.info(f"fetched from ecopower: {res}")
                return res             
        except Exception as exception:
            _LOGGER.exception(f"cannot fetch api data from ecopower: {exception}") 

class DynPriceUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(  self, hass: HomeAssistant, entsoe_client: EntsoeApiClient, ecopower_client: EcopowerApiClient) -> None:
        """Initialize."""
        self.entsoeapi   = entsoe_client
        self.ecopowerapi = ecopower_client
        self.platforms = []
        self.lastentsoefetch = 0
        self.lastecopwrtecht = 0
        self.entsoecache = None
        self.ecopwrcache_c = None
        self.ecopwrcache_i = None
        self.entsoelastday = None
        self.ecopwrlastday = None
        self.cache = None # merged entsoe and ecopower data

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        now = time.time()
        zulutime = time.gmtime(now)
        if self.entsoeapi: 
            _LOGGER.info(f"checking if entsoe api update is needed or data can be retrieved from cache at zulutime: {zulutime}")
            # reduce number of cloud fetches
            if not self.entsoecache or ((now - self.lastentsoefetch >= 3600) and (zulutime.tm_hour >= 12) and (self.entsoelastday <= zulutime.tm_mday)):
                try:
                    res1 = await self.entsoeapi.async_get_data()
                    if res1:
                        self.lastfetch = now
                        self.entsoelastday = res1['lastday']
                        self.entsoecache = res1['points']
                except Exception as exception:
                    raise UpdateFailed() from exception
        if self.ecopowerapi:
            _LOGGER.info(f"checking if ecopower api update is needed or data can be retrieved from cache at zulutime: {zulutime}")
            # reduce number of cloud fetches
            if (not self.ecopwrcache_c) or (not self.ecopwrcache_i) or ((now - self.lastecopwrfetch >= 3600) and (zulutime.tm_hour >= 12) and (self.ecopwrlastday <= zulutime.tm_mday)):
                try:
                    res2 = await self.ecopowerapi.async_get_data(url = ECOPWR_DAYAHEAD_URL.format(CURVE=ECOPWR_CONSUMPTION))
                    if res2:
                        #self.lastecopwrfetch = now
                        #self.ecopwrlastday = res2['lastday']
                        self.ecopwrcache_c = res2['points']
                    res3 = await self.ecopowerapi.async_get_data(url = ECOPWR_DAYAHEAD_URL.format(CURVE=ECOPWR_INJECTION))
                    if res3:
                        self.lastecopwrfetch = now
                        self.ecopwrlastday = res3['lastday']
                        self.ecopwrcache_i = res3['points']
                except Exception as exception:
                    raise UpdateFailed() from exception
        # return combined cache dictionaries
        return {'entsoe': self.entsoecache, 'ecopower_consumption': self.ecopwrcache_c, 'ecopower_injection': self.ecopwrcache_i}



