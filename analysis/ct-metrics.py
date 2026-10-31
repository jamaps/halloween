# Census tract (2021) metrics for trick-or-treat tradeoff map
#   - hilliness: area-weighted mean slope (%) of 2023 TIN triangles in residential zones
#   - income: median household income before tax, 2020 (mibth20)
#   - parcel size: median area of regular (COMMON) parcels in residential zones

import geopandas as gpd
import pandas as pd
import numpy as np
import pyogrio

CRS = "EPSG:2952"  # NAD83(CSRS) / MTM zone 10, matches TIN, zoning, and parcels

CT_PATH = "/home/ja/Dropbox/sofc/project-archive/neighbourhood-income-toronto-2020/data-prep/2021data.geojson"
TIN_PATH = "/home/ja/Dropbox/maps/maps_2025mostly/triangular-irregular-network/2023_TIN.shp"
CHILDREN_PATH = "data/children-ct.csv"  # 2021 census profile, ages 5-9, 10-14, 0-14
ZONING_PATH = "local_data/zoning-area-2952.gpkg"
PARCELS_PATH = "local_data/property-boundaries-2952.gpkg"

# ground-oriented residential zones in By-law 569-2013
# (RA / RAC apartment zones left out - no doors to knock on)
RES_ZONES = ["R", "RD", "RS", "RT", "RM"]


# census tracts + income

ct = gpd.read_file(CT_PATH)[["ctuid", "mibth20", "hhlds21", "geometry"]].to_crs(CRS)
ct["income"] = pd.to_numeric(ct["mibth20"], errors="coerce")
ct.loc[ct["income"] <= 0, "income"] = np.nan
ct["hhlds"] = pd.to_numeric(ct["hhlds21"], errors="coerce")
ct = ct.drop(columns=["mibth20", "hhlds21"])


# residential zones, split by census tract

zones = gpd.read_file(ZONING_PATH, columns=["ZN_ZONE"])
zones = zones[zones["ZN_ZONE"].isin(RES_ZONES)]
res = gpd.overlay(ct[["ctuid", "geometry"]], zones[["ZN_ZONE", "geometry"]], how="intersection")
res_ct = res.dissolve("ctuid")[["geometry"]]  # CT clipped to residential zones
ct = ct.merge(
    res_ct.area.rename("res_area_m2"),
    left_on="ctuid", right_index=True, how="left",
)
ct["res_area_m2"] = ct["res_area_m2"].fillna(0)
ct["res_share"] = ct["res_area_m2"] / ct.area


# children per km2 of residential zoned area

kids = pd.read_csv(CHILDREN_PATH, skiprows=7, dtype={"COL0": str})
kids = kids.rename(columns={"COL0": "ctuid", "COL1": "age_5_9", "COL2": "age_10_14", "COL3": "age_0_14"})
kids["kids_5_14"] = kids["age_5_9"] + kids["age_10_14"]
ct = ct.merge(kids[["ctuid", "kids_5_14", "age_0_14"]].rename(columns={"age_0_14": "kids_0_14"}), on="ctuid", how="left")
res_km2 = ct["res_area_m2"].where(ct["res_area_m2"] > 0) / 1e6
ct["kids_5_14_km2"] = ct["kids_5_14"] / res_km2
ct["kids_0_14_km2"] = ct["kids_0_14"] / res_km2
print("residential zone pieces:", len(res))


# parcels: assign by representative point to residential zone x CT

parcels = gpd.read_file(PARCELS_PATH, columns=["FEATURE_TYPE"])
parcels = parcels[parcels["FEATURE_TYPE"] == "COMMON"]
parcels["area_m2"] = parcels.area
pts = gpd.GeoDataFrame(parcels[["area_m2"]], geometry=parcels.representative_point(), crs=CRS)
pts = gpd.sjoin(pts, res[["ctuid", "geometry"]], predicate="within", how="inner")
pts = pts[~pts.index.duplicated()]
print("residential parcels:", len(pts))

parcel_stats = pts.groupby("ctuid")["area_m2"].agg(
    parcel_n="count",
    parcel_median_m2="median",
    parcel_mean_m2="mean",
)
ct = ct.merge(parcel_stats, left_on="ctuid", right_index=True, how="left")


# hilliness: TIN triangle centroids in residential zone x CT, area-weighted slope

tin = pyogrio.read_dataframe(TIN_PATH, columns=["Ptg_Slope"])
tin = tin.set_crs(CRS, allow_override=True)
tri = gpd.GeoDataFrame(
    {"slope": tin["Ptg_Slope"].to_numpy(), "w": tin.area.to_numpy()},
    geometry=tin.centroid.to_numpy(), crs=CRS,
)
del tin
print("TIN triangles:", len(tri))

def weighted_slope(tri_in, key):
    g = tri_in.assign(sw=tri_in["slope"] * tri_in["w"]).groupby(key)
    return g["sw"].sum() / g["w"].sum()

# all land in the CT (includes ravines) - for comparison
tri_ct = gpd.sjoin(tri, ct[["ctuid", "geometry"]], predicate="within", how="inner")
ct = ct.merge(weighted_slope(tri_ct, "ctuid").rename("slope_all_pct"), left_on="ctuid", right_index=True, how="left")
del tri_ct

# residential zones only - the streets you'd actually walk
tri_res = gpd.sjoin(tri, res_ct.reset_index(), predicate="within", how="inner")
ct =ct.merge(weighted_slope(tri_res, "ctuid").rename("slope_res_pct"), left_on="ctuid", right_index=True, how="left")
del tri_res


# output

ct = ct.round({
    "res_area_m2": 0, "res_share": 3,
    "kids_5_14_km2": 0, "kids_0_14_km2": 0,
    "parcel_median_m2": 1, "parcel_mean_m2": 1,
    "slope_all_pct": 2, "slope_res_pct": 2,
})

ct.drop(columns="geometry").to_csv("data/ct-metrics.csv", index=False)

web = ct.to_crs("EPSG:4326")
web["geometry"] = web.simplify(0.00005)
web.to_file("data/ct-metrics.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

# CTs clipped to residential zones, dropping CTs with no residential parcels
clip = gpd.GeoDataFrame(
    ct.drop(columns="geometry").merge(res_ct, left_on="ctuid", right_index=True),
    geometry="geometry", crs=CRS,
)
clip = clip[clip["parcel_n"] > 0]
clip.to_file("data/ct-res-metrics-2952.gpkg", driver="GPKG", layer="ct_res_zones")
clip = clip.to_crs("EPSG:4326")
clip["geometry"] = clip.simplify(0.00005)
clip.to_file("data/ct-res-metrics.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)
print("CTs with residential parcels:", len(clip))

print(ct.drop(columns="geometry").describe().T)
