# ecopower_dynamic_grid_prices

--------

## ATTENTION !!! : This integration is only meant for a limited group of ecopower customers that have a dynamic prices contract with hourly changing prices (day-ahead-prices). Normal Ecopower customers should not use this integration !!

## ATTENTION: As Ecopower has dropped support for its API, I suggest you may use my other https://github.com/infradom/dynamic_grid_prices integration that can compute the ecopower prices from the Entsoe prices

---------

This integration will periodically pull the dynamic grid prices from the Belgian Ecopower API.
I know similar integrations exist, but this one wont need a dependency on node-red. 
The Nordpool integration is a good alternative, but has no knowledge of the ecopower prices.
I also have a prototype integration for Entsoe that could be used.

## Disclaimer:
 - Errors in this software can have a significant impact on your electricity bill.
 The authors cannot be held liable for any financial or other damage caused by the use of this software. 
 - Ecopower has not been involved in the development of this software and cannot be held responsible for any malfunctions.


## Ecopower data source (Ecopower customers only)
This API provides the actual day-ahead prices that Ecopower will charge for a dynamic contract.


# Installation

## HACS install
This custom integration should appear soon in the HACS default store. 
As long as this is not visible,  go to HACS > integrations tab, click on the 3 dots in the top right corner, select custom repositories and add the https://github.com/infradom/ecopower_dynamic_grid_prices url to the repositories, with category 'integration'. A restart is required to load the integration and make it visible.

## Manual install
You can also install this also manually by copying the custom_components/ecopower_dynamic_grid_prices folder to your home assistant's config/custom_components folder. A restart your HA software may be required.
Then under settings->devices&services, press the 'add integration button' (bottom right), type or select EcopowerPrices 
A config dialog will be displayed.

# Configuration parameters:

- Authentication code for the Ecopower API: contact Ecopower to obtain a value for this token. If left empty, you must provide a backup source entity (e.g. from the nordpool integration)
- API curve id's for consumption and injection (obtained from Ecopower). Just enter the number, not the url
- (optional) Backup source flag: tick this box if you want to configure a backup source of information
- (optional) Test API flag: tick this box if you want to use the Ecopower test API (not for production !)

# Configuration parameters backup source:

 - entity id (used in case ecopower API would be down). Please note that the backup source must be configured so that it provides cost in € per kWh, without VAT. This has only been tested for the nordpool integration that has typically a entity id name like 'sensor.nordpool_kwh_be_eur_3_10_0' 
- grid operators may charge different prices than the ones published on the backup source. This integration allows you to declare factors A, B, C, D for some customization or the prices published on the backup source:
  - consume cost: Cost = A * (published_price + B)
  - injection fee:  Fee = C * (published_price - D)
Note that depending on the taxation, these simple scaling formulas may not correctly provide the real price in your country. They just allow us to have rough feeling of the consumption and injection price.

# Known problems
- Configuration menu: Entering scaling factors or offsets that contain zero's does not always work due to an error in HA. Use the arrow keys (and additonal less relevant non-zero digits) as a workaround.
- If your config menues have incomplete descriptions, make sure to clear your browser cache for this site.

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



