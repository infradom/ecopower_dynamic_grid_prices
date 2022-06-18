"""Constants for the DynGridPrices integration."""

DOMAIN = "dynamic_grid_prices_solar"

ENTSOE_DAYAHEAD_URL = "https://transparency.entsoe.eu/api?securityToken={TOKEN}&documentType=A44&in_Domain={AREA}&out_Domain={AREA}&periodStart={START}&periodEnd={END}"
ECOPWR_DAYAHEAD_URL = ""
ENTSOE_HEADERS = {"Content-type": "application/xml; charset=UTF-8"}
ECOPWR_HEADERS = {"Content-type": "application/json; charset=UTF-8"}

ATTRIBUTION = '@infradom'

NAME = "DynGridPricesSolar"
DEFAULT_NAME = DOMAIN
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"
ISSUE_URL = "https://github.com/infradom/dynamic_grid_prices_solar/issues"


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""

# configuration options
CONF_ENTSOE_TOKEN    = "entsoe_token"
CONF_ENTSOE_AREA     = "entsoe_area"
CONF_ENTSOE_FACTOR_A = "entsoe_factor_A"
CONF_ENTSOE_FACTOR_B = "entsoe_factor_B"
CONF_ENTSOE_FACTOR_C = "entsoe_factor_C"
CONF_ENTSOE_FACTOR_D = "entsoe_factor_D"
CONF_NAME            = "name"


SENSOR = "sensor"
PLATFORMS: list[Platform] = [SENSOR]

