# dynamic_grid_prices_solar
 
# dynamic_grid_prices_solar

Work in progress ! This will become a HomeAssistant integration

This integration will periodically pull the dynamic grid prices from the https://transparency.entsoe.eu API platform.
(https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html)
In order to use this, you will need to create a login and request an API token so that the integration can access the day-ahead-prices.


# configuration parameters:
- API authentication token
- area code (see https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html#_areas)
- grid operators may charge different prices than the ones published on entsoe. This integration allows to declare factors A, B, C, D for some customization:
  - consume cost: Cost = A * published_price + B
  - injection fee:  Fee = C * published_price + D



 