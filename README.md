# ecopower_dynamic_grid_prices


Work in progress ! This will become a HomeAssistant integration. 
FOR THE TIME BEING, IT IS VERY INCOMPLETE AND UNTESTED

This integration will periodically pull the dynamic grid prices from the Belgian Ecopower (trial) API.
I know similar integrations exist, but this one wont need a dependency on node-red. 
The Nordpool integration is a good alternative, but has no knowledge of the ecopower prices.
I also have a prototype integration for Entsoe that could be used.


## Ecopower (trial) data source (Ecopower customers only)
This API provides the actual day-ahead prices that Ecopower will charge for a dynamic contract.
My current implementation assumes you have a single tarif, no support yet for day/night meter in this integration.

# Installation
This custom integration cannot be installed through HACS yet, as we feel it is still too experimental.
You can install it manually by copying the custom_components/ecopower_dynamic_grid_prices folder to your home assistant's config/custom_components folder. A restart your HA software may be required.
Then under settings->devices&services, press the 'add integration button', type or select EcopowerGridPrices 
A config dialog will be displayed.

# Configuration parameters:

- Authentication code for the Ecopower API: contact Ecopower to obtain a value for this token. If left empty, you must provide a backup source entity (e.g. from the nordpool integration)
- (optional) Backup source entity id (used in case ecopower API would be down). Please note that the backup source must be configured so that it provides cost in € per kWh, without VAT. This has only been tested for the nordpool integration that has typically a entity id name like 'sensor.nordpool_kwh_be_eur_3_10_0' 
- grid operators may charge different prices than the ones published on the backup source. This integration allows you to declare factors A, B, C, D for some customization or the prices published on the backup source:
  - consume cost: Cost = A * (published_price + B)
  - injection fee:  Fee = C * (published_price - D)
Note that depending on the taxation, these simple scaling formulas may not correctly provide the real price in your country. They just allow us to have rough feeling of the consumption and injection price.

# Known problems
Configuration menu: Entering scaling factors or offsets that contain zero's does not always work due to an error in HA. Use the arrow keys (and additonal non-zero digits) as a workaround.

# Entities created:
This integration will create entitites for the Ecopower injection and consumption prices.
The entities contain an attribute list with the detailed day-ahead prices (per hour or per 15 minutes).
The attribute list is made compatible with the NordPool attributes, but the tomorrow entries have been added to the today list.
Besides the ecopower consumption and injection entities, it also creates backup entities (just to verify the correct scaling of the backup entity)
Additional entities will be created in future versions to make your automations easier.

# Apexchart Pricing Dashboard Card:
The integration makes it easy to create an apexchart graph using the raw_today attribute
For information on how to instaal custom:apexchart, see the appropriate website.
My very simple initial try uses this yaml code:

```
type: custom:apexcharts-card
experimental:
  color_threshold: true
graph_span: 48h
header:
  title: Electricity Price - Ecopower Injection
  show: true
span:
  start: day
  offset: +0d
now:
  show: true
  label: Now
yaxis:
  - decimals: 2
series:
  - entity: sensor.ecopower_injection_price
    type: column
    float_precision: 3
    data_generator: |
      return entity.attributes.raw_today.map((entry) => {
        return [new Date(entry.start), entry.value];
      });
    color_threshold:
      - value: 0
        color: green
        opacity: 1
      - value: 0.3
        color: yellow
      - value: 0.4
        color: red


```


# Disclaimer:
 Errors in this software can have a significant impact on your electricity bill.
 The authors cannot be held liable for any financial or other damage caused by the use of this software. 
