"""Config flow for DynGridPricesSolar integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
#from homeassistant.helpers import device_registry as dr, entity_registry as er

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN, NAME, CONF_NAME
from .const import ECOPWR_DAYAHEAD_URL, ECOPWR_DAYAHEAD_URL_ACC
from .const import CONF_ECOPWR_TOKEN, CONF_ECOPWR_API_C, CONF_ECOPWR_API_I, CONF_TEST_API
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

            valid1 = await self._test_credentials( ecopwr_token, curve_c, curve_i, test_api )
            if valid1: self.user_input = user_input

            if valid1:
                return self.async_create_entry( title=user_input[CONF_NAME], data=user_input )
            else:
                self._errors["base"] = "auth"
                _LOGGER.error("cannot authenticate auth - did you provide the correct API token ")
            return self.async_abort(reason="cannot_authenticate")
        else:
            user_input = {}
            # Provide defaults for form
            user_input[CONF_NAME]            = NAME
            user_input[CONF_ECOPWR_TOKEN]    = ""
            user_input[CONF_ECOPWR_API_C]    = ""
            user_input[CONF_ECOPWR_API_I]    = ""
            user_input[CONF_TEST_API]        = False
            return await self._show_config_form(user_input)



    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form( step_id="user",
            data_schema=vol.Schema(
                {   vol.Required(CONF_NAME,            default = user_input[CONF_NAME]): cv.string,
                    vol.Required(CONF_ECOPWR_TOKEN,    default = user_input[CONF_ECOPWR_TOKEN]): cv.string,
                    vol.Required(CONF_ECOPWR_API_C,    default = user_input[CONF_ECOPWR_API_C]): cv.string,
                    vol.Required(CONF_ECOPWR_API_I,    default = user_input[CONF_ECOPWR_API_I]): cv.string,
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
            else: url = ECOPWR_DAYAHEAD_URL
            res = await client.async_get_data(url.format(CURVE=curve_c))
            if len(res)>0: return True
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error(e,"ecopower credentials failed")
        return False







