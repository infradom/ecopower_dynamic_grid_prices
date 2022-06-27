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
from .const import STARTUP_MESSAGE, CONF_ECOPWR_TOKEN
from .const import ECOPWR_CONSUMPTION, ECOPWR_INJECTION, ECOPWR_HEADERS, ECOPWR_DAYAHEAD_URL
from .const import DOMAIN, PLATFORMS, SENSOR, CONF_BACKUP_SOURCE, CONF_BACKUP_FACTOR_A, CONF_BACKUP_FACTOR_B, CONF_BACKUP_FACTOR_C, CONF_BACKUP_FACTOR_D

# TODO List the platforms that you want to support.

SCAN_INTERVAL = timedelta(seconds=10)
UPDATE_INTERVAL = 900  # update data entities and addtibutes aligned to X seconds interval
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


    ecopower_client = None
    ecopwr_token = entry.data.get(CONF_ECOPWR_TOKEN)
    if ecopwr_token:
        ecopower_session = async_get_clientsession(hass)
        ecopower_client = EcopowerApiClient(ecopower_session, ecopwr_token)

    coordinator = DynPriceUpdateCoordinator(hass, ecopower_client = ecopower_client, entry = entry)
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
    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self._token = token
        self._session = session

    async def async_get_data(self, url: str = ECOPWR_DAYAHEAD_URL.format(CURVE=ECOPWR_CONSUMPTION) ) -> dict:
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
                bucketDuration = xpars['bucketDuration']
                if bucketDuration:
                    series = xpars['values']
                    seconds = bucketDuration * 60 # 900
                    for point in series:
                        if point["valueStatus"] == "valid": price = float(point["value"])*0.001 # convert source to kWh
                        zulutime = datetime.strptime(point["date"],'%Y-%m-%dT%H:%M:%S+00:00').replace(tzinfo=timezone.utc)
                        timestamp = zulutime.timestamp()
                        localtime = datetime.fromtimestamp(timestamp)
                        _LOGGER.info(f"{(zulutime.day, zulutime.hour, zulutime.minute,)} zulutime={datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()}Z localtime={datetime.fromtimestamp(timestamp).isoformat()} price={price}" )
                        res['points'][(zulutime.day, zulutime.hour, zulutime.minute,)] = {"price": price, "interval": seconds, "zulutime": datetime.fromtimestamp(timestamp, tz=timezone.utc), "localtime": datetime.fromtimestamp(timestamp)}
                        if zulutime.day > res['lastday']: res['lastday'] = zulutime.day
                _LOGGER.info(f"fetched from ecopower: {res}")
                return res             
        except Exception as exception:
            _LOGGER.exception(f"cannot fetch api data from ecopower: {exception}") 


class DynPriceUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(  self, hass: HomeAssistant, ecopower_client: EcopowerApiClient, entry: ConfigEntry) -> None:
        """Initialize."""
        self.ecopowerapi = ecopower_client
        self.platforms = []
        self.lastbackupfetch = 0
        self.lastecopwrtecht = 0
        self.backupcache_c = None
        self.backupcache_i = None
        self.backupcache = None
        self.ecopwrcache_c = None
        self.ecopwrcache_i = None
        self.backuplastday = 0
        self.ecopwrlastday = 0
        self.cache = None # merged entsoe and ecopower data
        self.lastcheck = 0
        self.hass = hass
        self.entry = entry

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Update data via library."""
        now = time.time()
        zulutime = time.gmtime(now)
        slot = int(now)//UPDATE_INTERVAL # integer division in python3.x
        if (slot > self.lastcheck) or not(self.ecopwrcache_c and self.backupcache) : # do nothing unless we are in a new time slot, except on startup
            self.lastcheck = slot 
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

            backupentity = self.entry.data.get(CONF_BACKUP_SOURCE)
            if backupentity:
                if (not self.backupcache) or ((now - self.lastbackupfetch >= 3600) and (zulutime.tm_hour >= 12) and (self.backuplastday <= zulutime.tm_mday)):

                    factor_a = self.entry.data.get(CONF_BACKUP_FACTOR_A)
                    factor_b = self.entry.data.get(CONF_BACKUP_FACTOR_B)
                    factor_c = self.entry.data.get(CONF_BACKUP_FACTOR_C)
                    factor_d = self.entry.data.get(CONF_BACKUP_FACTOR_D)
                    _LOGGER.info(f"loadingbackup source {backupentity}")
                    backupstate = self.hass.states.get(backupentity)
                    if backupstate: 
                        backupdata = backupstate.attributes['raw_today'] 
                        self.backupcache_c = {}
                        self.backupcache_i = {}
                        self.backupcache = {}
                        overwrite = (len(self.ecopwrcache_i) < 24*4) or (len(self.ecopwrcache_c) <24*4) 
                        if overwrite:  _LOGGER.error(f"fetched ecopower results to not cover a full day")
                        for val in backupdata:
                            value = val['value']
                            zulustart = val['start']
                            timestamp = datetime.timestamp(zulustart)
                            localstart = datetime.fromtimestamp(timestamp)
                            day = zulustart.day
                            hour = zulustart.hour
                            minute = zulustart.minute
                            interval = 3600
                            _LOGGER.info(f"loading backup data: {timestamp} {value} zulutime: {zulustart} localtime: {localstart}")
                            self.backupcache[(day, hour, minute,)]   = {"price": value, "interval": interval, "zulutime": zulustart, "localtime": localstart}
                            if overwrite:
                                pass
                                    #self.ecopwrcache_c[(day, hour, minute,)] = {"price": value, "interval": interval, "zulutime": zulustart, "localtime": localstart}
                                    #self.ecopwrcache_i[(day, hour, minute,)] = {"price": value, "interval": interval, "zulutime": zulustart, "localtime": localstart}
                            self.backupcache_c[(day, hour, minute,)] = {"price": factor_a * (value + factor_b), "interval": interval, "zulutime": zulustart, "localtime": localstart}
                            self.backupcache_i[(day, hour, minute,)] = {"price": factor_c * (value - factor_d), "interval": interval, "zulutime": zulustart, "localtime": localstart}

        # return combined cache dictionaries
        return {'backup_ecopower_consumption': self.backupcache_c, 
                'backup_ecopower_injection': self.backupcache_i, 
                'backup': self.backupcache,
                'ecopower_consumption': self.ecopwrcache_c, 
                'ecopower_injection': self.ecopwrcache_i}



