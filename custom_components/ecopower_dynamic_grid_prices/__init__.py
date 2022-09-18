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
    async_import_statistics,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, CURRENCY_EURO

import async_timeout
import aiohttp, asyncio
import logging
import datetime
import pandas
from scipy import stats
from .const import STARTUP_MESSAGE, CONF_ECOPWR_TOKEN, CONF_TEST_API
from .const import ECOPWR_HEADERS, ECOPWR_DAYAHEAD_URL, ECOPWR_DAYAHEAD_URL_ACC
from .const import DOMAIN, PLATFORMS, SENSOR
from .const import CONF_ECOPWR_API_C, CONF_ECOPWR_API_I

SCAN_INTERVAL = datetime.timedelta(seconds=20)  # TODO

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
    ecopower_client = EcopowerApiClient(
        ecopower_session, ecopwr_token, curve_c, curve_i, test_api
    )

    coordinator = DynPriceUpdateCoordinator(hass, ecopower_client=ecopower_client)
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
        self, session: aiohttp.ClientSession, token: str, curve_c, curve_i, test_api
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
                df.index = pandas.to_datetime(df.index).tz_convert(tz="UTC").floor("H")
                df = df.drop_duplicates(ignore_index=False)
                df["value"] = df["value"] * 10**-3  # MWh -> KWh
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

    def __init__(self, hass: HomeAssistant, ecopower_client: EcopowerApiClient) -> None:
        """Initialize."""
        self.platforms = []
        self.ecopowerapi = ecopower_client
        self.hass = hass
        self.dt_last_data_point = pandas.Timestamp(year=1990, month=1, day=1, tz="UTC")
        self.dt_last_fetch = pandas.Timestamp(year=1990, month=1, day=1, tz="UTC")
        self.cache_c = None  # caching dict of timestamp to price
        self.cache_i = None # caching dict of timestamp to price
        self.zscore = None # number of standard deviations from the mean value
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)


    async def _async_update_data(self):
        """Update data via library."""

        now = pandas.Timestamp.utcnow()
        if (self.dt_last_data_point - now <= datetime.timedelta(hours=10)) and (
            self.dt_last_fetch - now <= datetime.timedelta(hours=1)
        ):
            # Get data from api
            df_c = await self.ecopowerapi.async_get_data(url=self.ecopowerapi._url_c)
            df_i = await self.ecopowerapi.async_get_data(url=self.ecopowerapi._url_i)

            self.dt_last_data_point = min(df_c.index.max(), df_i.index.max())
            _LOGGER.info(
                f"fetched ecopower api data with latest data from {self.dt_last_data_point}"
            )

            # insert data in statistics for use in charts
            await self._insert_statistics(df_c, "ecopower_consumption_price")
            await self._insert_statistics(df_i, "ecopower_injection_price")

            # caching for quick lookup
            self.cache_c = df_c["value"].to_dict()
            self.cache_i = df_i["value"].to_dict()

            # zscore to know if we are in a low price/high price moment
            self.zscore =  stats.zscore(df_c["value"]).round(decimals=3).to_dict()

        current_hour = now.floor("H")
        return {
            "ecopower_consumption_price": self.cache_c[current_hour],
            "ecopower_injection_price": self.cache_i[current_hour],
            "ecopower_zscore": self.zscore[current_hour],
        }


    async def _insert_statistics(self, df, name):
        """Insert historical statistics ."""
        aggs = {f"{ag}_value": ("value", ag) for ag in ["min", "mean", "max"]}
        df_hour = df.groupby(pandas.Grouper(freq="60Min")).agg(**aggs)

        # statistic_id = f"{DOMAIN}:{name}".lower()  # external statistic
        statistic_id = f"sensor.{name}".lower()

        _LOGGER.info(f"adding historical statistics for {statistic_id}")

        statistics = []
        for dt, mean, min, max in zip(
            df_hour.index,
            df_hour[f"mean_value"],
            df_hour[f"min_value"],
            df_hour[f"max_value"],
        ):
            statistics.append(
                StatisticData(
                    start=dt,
                    mean=mean,
                    min=min,
                    max=max,
                )
            )

        metadata = StatisticMetaData(
            has_mean=True,
            has_sum=False,
            name=name,
            # source=DOMAIN,
            source="recorder",
            statistic_id=statistic_id,
            unit_of_measurement=f"{CURRENCY_EURO}/{ENERGY_KILO_WATT_HOUR}",  #
        )
        _LOGGER.info(f"adding {len(statistics)} statistics for {statistic_id}")
        # async_add_external_statistics(self.hass, metadata, statistics)
        async_import_statistics(self.hass, metadata, statistics)







    # insert data in states
    # attr = {
    #     "unit_of_measurement": "€/kWh",  # TODO should be able to retreive this from id
    #     "device_class": "monetary",
    #     "friendly_name": "Ecopower Consumption Price",
    # }
    # await self._insert_states(df_c, "sensor.ecopower_consumption_price", attr)
    # attr = {'unit_of_measurement': '€/kWh', #TODO should be able to retreive this from id
    #         'device_class': 'monetary',
    #         'friendly_name': 'Ecopower Injection Price'}
    # await self._insert_states(df_i, 'sensor.ecopower_injection_price', attr)
    # return {"ecopower_consumption_price": df_c, "ecopower_injection_price": df_i}

    # async def _insert_states(self, df, entity_id, attr):
    #     """insert states directly, bypassing the normal process
    #     This function can be reduced significantly
    #     if StateMachine.async_set would allow a different timestamp than 'now'
    #     -> TODO make pull request to core
    #     """
    # from homeassistant.helpers.entity import FLOAT_PRECISION
    # from homeassistant.const import EVENT_STATE_CHANGED
    # from homeassistant.core import EventOrigin, Context, State
    # from homeassistant.util import dt as dt_util, ulid as ulid_util
    #     # def monkey_get(sel, entity_i: str):
    #     #     """Retrieve state of entity_id or None if not found.

    #     #     Async friendly.
    #     #     """
    #     #     val = sel._states.get(entity_i.lower())
    #     #     print("getting state")
    #     #     current_hour = pandas.Timestamp.utcnow().floor("H")
    #     #     if current_hour in val.attributes:
    #     #         # print(val.attributes[current_hour])
    #     #         return State(
    #     #             entity_i.lower(),
    #     #             val.attributes[current_hour],
    #     #             {
    #     #                 "unit_of_measurement": "€/kWh",  # TODO should be able to retreive this from id
    #     #                 "device_class": "monetary",
    #     #                 "friendly_name": "Ecopower Consumption Price",
    #     #             },
    #     #             current_hour,
    #     #             current_hour,
    #     #             None,
    #     #             False,
    #     #         )
    #     #     else:
    #     #         return val
    #     # from homeassistant.components.recorder.util import session_scope
    #     # from homeassistant.components.recorder.db_schema import States
    #     # with session_scope(hass=self.hass) as session:
    #     #     db_states = list(session.query(States))
    #     df.index = df.index.tz_convert(tz="UTC").floor("H")
    #     current_hour = pandas.Timestamp.utcnow().floor("H")
    #     df = df.drop_duplicates(ignore_index=False)
    #     now = dt_util.utcnow()
    #     last_changed = None
    #     old_state = self.hass.states.get(entity_id)
    #     if old_state is not None:
    #         if old_state.last_updated >= df.index.max():
    #             # do not update if there is no new data
    #             _LOGGER.info(f"no new data for {entity_id}")
    #             return
    #     _LOGGER.info(f"updating state for {entity_id}")
    #     # monkeypatch state
    #     # self.hass.states.get = monkey_get.__get__(self.hass.states)
    #     # self.hass.states._states[entity_id] = State(
    #     #         entity_id,
    #     #         '6',
    #     #         df["value"].to_dict(), #.update(attr),
    #     #         None, #last_changed,
    #     #         None, #last_updated,
    #     #         None, #context,
    #     #         old_state is None,
    #     #     )

    #     for last_updated, value in df["value"].iteritems():
    #         # old_state will be None on the first pass
    #         # old_state seems to be optional
    #         old_state = None  # self.hass.states._states.get(entity_id)
    #         new_state = f"{value:.{FLOAT_PRECISION}}"
    #         context = Context(id=ulid_util.ulid(dt_util.utc_to_timestamp(last_updated)))

    #         state = State(
    #             entity_id,
    #             new_state,
    #             attr,
    #             last_changed,
    #             last_updated,
    #             context,
    #             old_state is None,
    #         )
    #         if old_state is not None:
    #             old_state.expire()
    #         #TODO this is temp as it is not efficient
    #         if last_updated==current_hour:
    #             print('setting current state')
    #             self.hass.states._states[entity_id] = state
    #             # State(
    #             #         entity_id,
    #             #         '6',
    #             #         df["value"].to_dict(), #.update(attr),
    #             #         None, #last_changed,
    #             #         None, #last_updated,
    #             #         None, #context,
    #             #         old_state is None,
    #             #     )
    #         # self.hass.states.async_set(
    #         #     entity_id, value, attr, False, None,last_updated        )
    #         self.hass.states._bus.async_fire(
    #             EVENT_STATE_CHANGED,
    #             {"entity_id": entity_id, "old_state": old_state, "new_state": state},
    #             EventOrigin.local,
    #             context,
    #             time_fired=now,
    #         )
