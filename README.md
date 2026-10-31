# Where to Trick or Treat in Toronto?

Fun Halloween map to help find your optimal trick-or-treating neighbourhood.

## How it works

First created a grid of hexagons (100m apart) across the city, and only kept hexes where at least 10% of the hex is zoned residential (R, RD, RS, RT, RM, RA, or RAC). 

For each hex, summarized everything within a 500m buffer of it (about a 10-minute walk). Rather than buffering ~45,000 points one by one, everything is put on a 10m raster and then convolved with a 500m disk, which gives the same result but much faster.

Data variables:

- **Kid density** - children aged 5-14 per km² of land. Census counts from dissemination areas (DAs), spread evenly over each DA (areal interpolation). 2021 census data.
- **Family households** - % of households that are couples or one-parent families with children. Also from DAs. Also 2021 census data.
- **Household income** - median after-tax household income, household-weighted average of DAs. Also 2021 census data, of 2020 annual income.
- **Lot size** - mean area of residential parcels whose centre is in the 500m buffer area.
- **Flat terrain** - mean slope of the ground in residential zones, weighted by triangle area, from the City's 2023 TIN (triangulated elevation surface).
- **Sidewalks** - % of street length (local, collector, arterial) with sidewalks on both sides. From City's sidewalk coverage data.
- **Car trips** - % of local residents' trips made by car (auto driver, passenger, taxi, ride-hail), trip-weighted from Transportation Tomorrow Survey (TTS) zones.

The 100m hexes are then averaged up to 200m hexes for the interactive map, and small holes (4 hexes or fewer, or a missing hex with 5+ neighbours) are filled with the average of the hexes around them.

On the map, each variable is converted to a percentile, multiplied by its slider weight, and summed. The colour is the percentile of that weighted score. The arrows next to each slider flip whether more or less of something is better.

## Data sources

- Statistics Canada, 2021 Census of Population (dissemination areas: age, households by type, income) and DA boundaries
- City of Toronto Open Data: zoning by-law (current, plus the 2014 version for residential zones missing from the current layer), property boundaries, pedestrian network (2019; sidewalk sides by street segment), 2023 TIN (elevation)
- Transportation Tomorrow Survey (TTS) 2022/2023
- OpenStreetMap: basemap and labels (shortbread vector tiles)


## Caveats

This is not meant to be taken too seriously! Zoning is a rough stand-in for what's actually built, the census data is from 2021, and nothing here can tell you which houses actually have the best decorations or full-size chocolate bars.
