"""Config flow for DynGridPricesSolar integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
#from homeassistant.helpers import device_registry as dr, entity_registry as er

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN, NAME, CONF_NAME, CONF_BACKUP
from .const import CONF_BACKUP_FACTOR_A, CONF_BACKUP_FACTOR_B, CONF_BACKUP_FACTOR_C, ECOPWR_DAYAHEAD_URL, ECOPWR_DAYAHEAD_URL_ACC
from .const import CONF_BACKUP_FACTOR_D, CONF_ECOPWR_TOKEN, CONF_BACKUP_SOURCE, CONF_ECOPWR_API_C, CONF_ECOPWR_API_I, CONF_TEST_API
from .__init__ import EcopowerApiClient

_LOGGER = logging.getLogger(__name__)



class DynPricesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Blueprint."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        # Uncomment the next 2 lines if only a single instance of the integration is allowed:
        # if self._async_current_entries():
        #     return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            ecopwr_token = user_input[CONF_ECOPWR_TOKEN]
            curve_c = user_input[CONF_ECOPWR_API_C]
            curve_i = user_input[CONF_ECOPWR_API_I]
            test_api = user_input[CONF_TEST_API]
            backupflag = user_input[CONF_BACKUP]

            valid1 = not ecopwr_token or await self._test_credentials( ecopwr_token, curve_c, curve_i, test_api )
            if valid1: self.user_input = user_input
            user_input[CONF_BACKUP_SOURCE]   = None
            if user_input[CONF_BACKUP]: 
                return await self.async_step_backup(user_input)
            if valid1:
                return self.async_create_entry( title=user_input[CONF_NAME], data=user_input )
            else:
                self._errors["base"] = "auth"
                _LOGGER.error("cannot authenticate auth - did you provide at least the API token or a valid backup entity?")
            return self.async_abort(reason="cannot_authenticate")
        else:
            user_input = {}
            # Provide defaults for form
            user_input[CONF_NAME]            = NAME
            user_input[CONF_BACKUP]          = False
            user_input[CONF_ECOPWR_TOKEN]    = ""
            user_input[CONF_ECOPWR_API_C]    = ""
            user_input[CONF_ECOPWR_API_I]    = ""
            user_input[CONF_TEST_API]        = False
            return await self._show_config_form(user_input)


    async def async_step_backup(self, user_input = None):
        if user_input[CONF_BACKUP_SOURCE] is not None:
            # validate
            backupentity = user_input[CONF_BACKUP_SOURCE]
            valid2 = self._test_backup(backupentity)
            if valid2: self.user_input = self.user_input | user_input
            if valid2: return self.async_create_entry( title=self.user_input[CONF_NAME], data=self.user_input )

        user_input[CONF_BACKUP_FACTOR_A] = 1.06  #0.001 *1.06 # scale to kWh
        user_input[CONF_BACKUP_FACTOR_B] = 0.142 # per kWh
        user_input[CONF_BACKUP_FACTOR_C] = 1.0001 #0.001 # scale to kWh
        user_input[CONF_BACKUP_FACTOR_D] = 0.0023   # per MWh
        return self.async_show_form( step_id="backup", data_schema=vol.Schema(
            {   vol.Optional(CONF_BACKUP_SOURCE,   default = user_input[CONF_BACKUP_SOURCE]): 
                        selector.EntitySelector( selector.EntitySelectorConfig(domain="sensor"),) ,
                vol.Optional(CONF_BACKUP_FACTOR_A, default = self.user_input[CONF_BACKUP_FACTOR_A]): float, # should be cv.positive_float
                vol.Optional(CONF_BACKUP_FACTOR_B, default = self.user_input[CONF_BACKUP_FACTOR_B]): float, # should be cv.positive_float                  
                vol.Optional(CONF_BACKUP_FACTOR_C, default = self.user_input[CONF_BACKUP_FACTOR_C]): float, # should be cv.positive_float
                vol.Optional(CONF_BACKUP_FACTOR_D, default = self.user_input[CONF_BACKUP_FACTOR_D]): float, # should be cv.positive_float
            } ), errors = self._errors )

    """
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return DynPricesOptionsFlowHandler(config_entry)
    """

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form( step_id="user",
            data_schema=vol.Schema(
                {   vol.Required(CONF_NAME,            default = user_input[CONF_NAME]): cv.string,
                    vol.Required(CONF_ECOPWR_TOKEN,    default = user_input[CONF_ECOPWR_TOKEN]): cv.string,
                    vol.Required(CONF_ECOPWR_API_C,    default = user_input[CONF_ECOPWR_API_C]): cv.string,
                    vol.Required(CONF_ECOPWR_API_I,    default = user_input[CONF_ECOPWR_API_I]): cv.string,
                    vol.Optional(CONF_BACKUP,          default = user_input[CONF_BACKUP]): bool, 
                    vol.Optional(CONF_TEST_API,        default = user_input[CONF_TEST_API]): bool, 
                }
            ),
            errors=self._errors,
        )


    async def _test_credentials(self, token, curve_c, curve_i, test_api):
        """Return true if credentials is valid."""
        #_LOGGER.info(f"testing credentials: {curve_c} {ECOPWR_DAYAHEAD_URL}")
        try:
            session = async_create_clientsession(self.hass)
            client = EcopowerApiClient(session, token, curve_c, curve_i, test_api)
            if test_api : url = ECOPWR_DAYAHEAD_URL_ACC
            else:         url = ECOPWR_DAYAHEAD_URL
            res = await client.async_get_data(url.format(CURVE=curve_c))
            if res: return True
        except Exception:  # pylint: disable=broad-except
            _LOGGER.error("ecopower credentials failed")
        return False

    def _test_backup(self, backupentity):
        backupstate = self.hass.states.get(backupentity)
        check = 'raw_today' # attribute to check whether backup entity is valid
        if backupstate and backupstate.attributes[check] :
            _LOGGER.info(f"backup entity {backupentity} state: {backupstate}")
            _LOGGER.info(f"backup entity attritubes {backupstate.attributes[check]} ")
            return True
        else: 
            _LOGGER.error(f"cannot find valid backup entity {backupentity} or entity has no valid attribute {check} - state: {backupstate}")
            return False


"""
class DynPricesOptionsFlowHandler(config_entries.OptionsFlow):
    #Blueprint config flow options handler

    def __init__(self, config_entry):
        # Initialize HACS options flow.
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
        # Manage the options.
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        # Handle a flow initialized by the user.
        if user_input is not None:
            self.options.update(user_input)
            return await self._update_options()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                { vol.Optional(CONF_BACKUP_SOURCE,   default = user_input[CONF_BACKUP_SOURCE]): 
                      selector.EntitySelector( selector.EntitySelectorConfig(domain="sensor"),) ,
                }
            ),
        )

    async def _update_options(self):
        # Update config entry options.
        return self.async_create_entry(
            title=self.config_entry.data.get(CONF_NAME), data=self.options
        )

"""



