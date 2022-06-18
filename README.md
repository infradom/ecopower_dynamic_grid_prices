# dynamic_grid_prices_solar


Work in progress ! This will become a HomeAssistant integration

This integration will periodically pull the dynamic grid prices from the https://transparency.entsoe.eu API platform.
I know similar integrations exist, but this one wont need a dependency on node-red.
In order to use this, you will need to create a entsoe platform login and request an API token so that the integration can access the day-ahead-prices.


# configuration parameters:
- API authentication token (see https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html#_authentication_and_authorisation 
- area code: for Belgium this is 10YBE----------2 (for other areas, see https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html#_areas)
- grid operators may charge different prices than the ones published on entsoe. This integration allows to declare factors A, B, C, D for some customization:
  - consume cost: Cost = A * published_price + B
  - injection fee:  Fee = C * published_price - D



 
