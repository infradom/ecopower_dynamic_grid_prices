# ecopower_dynamic_grid_prices

--------

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

- Authentication code for the Ecopower API: contact Ecopower to obtain a value for this token. 
- API curve id's for consumption and injection (obtained from Ecopower). Just enter the number, not the url
- (optional) Test API flag: tick this box if you want to use the Ecopower test API (not for production !)

# Entities created:
This integration will create 3 entitites:
- the Ecopower injection price
- the Ecopower consumption price
- the price zscore, which indicates if the price for the current hour is low (negative) or high (positive) compared to the other hourly prices (for more info on zscore, see https://en.wikipedia.org/wiki/Standard_score)

# Apexchart Pricing Dashboard Card:
The integration makes it easy to create an apexchart graph 
For information on how to install custom:apexchart, see the appropriate website.
My very simple initial try uses this yaml code:

```
type: custom:apexcharts-card
header:
  show: true
  title: Ecopower consumption-injection price
graph_span: 48h
span:
  start: day
  offset: '-0h'
now:
  show: true
  label: Now
yaxis:
  - decimals: 2
series:
  - entity: sensor.ecopower_consumption_price
    type: column
    float_precision: 2
    statistics:
      type: mean
      period: hour
      align: start
    show:
      legend_value: false
  - entity: sensor.ecopower_injection_price
    type: column
    float_precision: 2
    statistics:
      type: mean
      period: hour
      align: start
    show:
      legend_value: false

```



