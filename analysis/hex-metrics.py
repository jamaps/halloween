# Rolling 500m (~10 min walk) window metrics on a 100m hex grid in residential zones
# (R-type zone in either the current zoning by-law layer or the 2014 one)
#   - kids_5_14_km2: children 5-14 per km2 of land (areal interpolation from DAs)
#   - hh_kids_pct: % of households that are couple or one-parent families with children (DAs)
#   - income: median after-tax household income, household-weighted areal interpolation from DAs
#   - parcel_mean_m2: mean area of residential parcels with centroid in window
#   - slope_all_pct / slope_res_pct: triangle-area-weighted slope, all land / R zones only
#   - sidewalk_pct: % of street length with sidewalks on both sides (local, collector, arterial)
#   - car_pct: % of trips by car (TTS 2022, by home zone), trip-weighted areal interpolation
#
# Windows are computed by binning everything onto a 10m raster and convolving with a
# RADIUS disk, then sampling at hex points - equivalent to buffering each point.

import subprocess

import geopandas as gpd
import pandas as pd
import numpy as np
import pyogrio
import shapely
from rasterio import features
from rasterio.transform import from_origin
from scipy.signal import fftconvolve

CRS = "EPSG:2952"

DA_PATH = "/home/ja/Dropbox/sofc/project-archive/who-are-streets-for/local_data/mia/dissemination area/lda_000b21a_e.shp"
DA_DATA_PATH = "data/da-children-income.txt"  # 2021 census profile, CHASS export
TIN_PATH = "/home/ja/Dropbox/maps/maps_2025mostly/triangular-irregular-network/2023_TIN.shp"
ZONING_PATH = "local_data/zoning-area-2952.gpkg"
ZONING_2014_PATH = "local_data/zoning-2014-wgs84/ZONING_ZONE_CATAGORIES_WGS84.shp"  # some R zones missing from current
PARCELS_PATH = "local_data/property-boundaries-2952.gpkg"
PEDNET_PATH = "../toronto-sidewalks/Pedestrian Network Data - 4326.gpkg"
TTS_ZONES_PATH = "/home/ja/Dropbox/sofc/projects/transportation-tomorrow-survey/data/tts2022zones.geojson"
TTS_METRICS_PATH = "/home/ja/Dropbox/sofc/projects/transportation-tomorrow-survey/data/metrics_tts2022.csv"

RES_ZONES = ["R", "RD", "RS", "RT", "RM", "RA", "RAC"]  # incl. apartment zones

HEX_SPACING = 100  # m between neighbouring points
RADIUS = 500  # m, ~10 min walk
CELL = 10  # m raster resolution


# inputs

# DA data: whitespace-delimited, COL0..COL16 (see header of file); n/a -> NaN
da_cols = {
    0: "dauid", 3: "age_5_9", 4: "age_10_14", 5: "income", 6: "hhlds",
    9: "hh_couple_kids", 11: "hh_one_parent",
}
da_data = pd.read_csv(DA_DATA_PATH, sep=r"\s+", skiprows=21, header=None, dtype=str, na_values="n/a")
da_data = da_data[da_data[0].str.len() == 8][list(da_cols)].rename(columns=da_cols)
for c in da_cols.values():
    if c != "dauid":
        da_data[c] = pd.to_numeric(da_data[c], errors="coerce")
da_data["kids_5_14"] = da_data["age_5_9"] + da_data["age_10_14"]
da_data["hh_kids"] = da_data["hh_couple_kids"] + da_data["hh_one_parent"]

da = pyogrio.read_dataframe(DA_PATH, columns=["DAUID"], where="DAUID LIKE '3520%'").to_crs(CRS)
da["geometry"] = da.make_valid()
da = da.merge(da_data, left_on="DAUID", right_on="dauid", how="left")
print("DAs:", len(da), "with data:", da["hhlds"].notna().sum())

zones = pd.concat([
    gpd.read_file(ZONING_PATH, columns=["ZN_ZONE"]),
    gpd.read_file(ZONING_2014_PATH, columns=["ZN_ZONE"]).to_crs(CRS),
])
res_union = shapely.intersection(
    zones.loc[zones["ZN_ZONE"].isin(RES_ZONES)].make_valid().union_all(),
    da.union_all(),
)
print("residential zoned km2:", round(res_union.area / 1e6, 1))
shapely.prepare(res_union)


# raster grid

xmin, ymin, xmax, ymax = da.total_bounds
xmin, ymin = np.floor([xmin - RADIUS, ymin - RADIUS])
xmax, ymax = np.ceil([xmax + RADIUS, ymax + RADIUS])
ncol = int((xmax - xmin) // CELL) + 1
nrow = int((ymax - ymin) // CELL) + 1
transform = from_origin(xmin, ymax, CELL, CELL)
cell_area = CELL * CELL
print("raster:", nrow, "x", ncol)

def to_rc(x, y):
    col = ((x - xmin) // CELL).astype(int)
    row = ((ymax - y) // CELL).astype(int)
    return row, col

def bin_points(x, y, w):
    grid = np.zeros((nrow, ncol))
    row, col = to_rc(x, y)
    np.add.at(grid, (row, col), w)
    return grid

def burn(geoms, values):
    return features.rasterize(
        zip(geoms, values), out_shape=(nrow, ncol), transform=transform,
        fill=0, dtype="float64",
    )

# DA counts spread evenly over each DA (per-cell share); suppressed DAs skipped
def burn_count(values):
    ok = values.notna().to_numpy()
    return burn(da.geometry[ok], (values / da.area * cell_area)[ok])

land = burn(da.geometry, np.ones(len(da))) * cell_area
kids_grid = burn_count(da["kids_5_14"])
has_hh = da["hh_kids"].notna() & da["hhlds"].notna()
hh_all_grid = burn_count(da["hhlds"].where(has_hh))
hh_kids_grid = burn_count(da["hh_kids"].where(has_hh))
has_inc = da["income"].notna() & da["hhlds"].notna()
hh_grid = burn_count(da["hhlds"].where(has_inc))
hhinc_grid = burn_count((da["hhlds"] * da["income"]).where(has_inc))
res_mask = burn([res_union], [1]).astype(bool)


# parcels in R zones

parcels = gpd.read_file(PARCELS_PATH, columns=["FEATURE_TYPE"])
parcels = parcels[parcels["FEATURE_TYPE"] == "COMMON"]
rp = parcels.representative_point()
in_res = shapely.contains_xy(res_union, rp.x, rp.y)
rp = rp[in_res]
parcel_area = parcels.area[in_res].to_numpy()
parcel_n_grid = bin_points(rp.x.to_numpy(), rp.y.to_numpy(), np.ones(len(rp)))
parcel_area_grid = bin_points(rp.x.to_numpy(), rp.y.to_numpy(), parcel_area)
print("residential parcels:", len(rp))
del parcels


# TIN triangles

tin = pyogrio.read_dataframe(TIN_PATH, columns=["Ptg_Slope"])
tc = tin.centroid
tx, ty = tc.x.to_numpy(), tc.y.to_numpy()
tw = tin.area.to_numpy()
ts = tin["Ptg_Slope"].to_numpy()
del tin, tc
ok = (tx >= xmin) & (tx < xmax) & (ty > ymin) & (ty <= ymax)
tx, ty, tw, ts = tx[ok], ty[ok], tw[ok], ts[ok]
tr, tcol = to_rc(tx, ty)
t_res = res_mask[tr, tcol]
w_grid = bin_points(tx, ty, tw)
sw_grid = bin_points(tx, ty, ts * tw)
w_res_grid = bin_points(tx[t_res], ty[t_res], tw[t_res])
sw_res_grid = bin_points(tx[t_res], ty[t_res], (ts * tw)[t_res])
print("TIN triangles:", len(tx))


# streets: sidewalk sides, lines split into ~CELL pieces

STREET_TYPES = ["Local", "Collector", "Minor Arterial", "Major Arterial"]

def sidewalk_sides(desc):
    d = str(desc).lower()
    if "both sides" in d:
        return 2.0
    if "only" in d:
        return 1.0
    if "partially on other side" in d:
        return 1.5
    if "partial sidewalk" in d:
        return 0.5
    if "no sidewalk" in d:
        return 0.0
    return np.nan  # under development, n/a, missing

ped = gpd.read_file(PEDNET_PATH, columns=["ROAD_TYPE", "SIDEWALK_DESCRIPTION"]).to_crs(CRS)
ped = ped[ped["ROAD_TYPE"].isin(STREET_TYPES)].explode(ignore_index=True)
ped["sides"] = ped["SIDEWALK_DESCRIPTION"].map(sidewalk_sides)

seg_len = ped.length.to_numpy()
n_pieces = np.maximum(np.ceil(seg_len / CELL).astype(int), 1)
idx = np.repeat(np.arange(len(ped)), n_pieces)
frac = (np.concatenate([np.arange(n) for n in n_pieces]) + 0.5) / n_pieces[idx]
sp = shapely.line_interpolate_point(ped.geometry.to_numpy()[idx], frac, normalized=True)
sx, sy = shapely.get_x(sp), shapely.get_y(sp)
sl = (seg_len / n_pieces)[idx]
ok = (sx >= xmin) & (sx < xmax) & (sy > ymin) & (sy <= ymax)
sx, sy, sl, idx = sx[ok], sy[ok], sl[ok], idx[ok]

sides = ped["sides"].to_numpy()[idx]
known = ~np.isnan(sides)
street_len_grid = bin_points(sx, sy, sl)
known_len_grid = bin_points(sx[known], sy[known], sl[known])
both_sides = known & (sides == 2)
both_len_grid = bin_points(sx[both_sides], sy[both_sides], sl[both_sides])
print("street segments:", len(ped), "km:", round(seg_len.sum() / 1000))
del ped, sp


# TTS 2022 car mode share, by home zone (drive = auto driver, passenger, taxi, rideshare)

tts = gpd.read_file(TTS_ZONES_PATH)[["TTS2022", "geometry"]].to_crs(CRS)
tts_m = pd.read_csv(TTS_METRICS_PATH)
tts_m["trips_car"] = tts_m[["trip_mode_prime_D", "trip_mode_prime_P", "trip_mode_prime_T", "trip_mode_prime_U"]].sum(axis=1)
tts = tts.merge(tts_m[["tts22_hhld", "trips_total", "trips_car"]], left_on="TTS2022", right_on="tts22_hhld", how="inner")
tts = tts[tts["trips_total"] > 0].cx[xmin:xmax, ymin:ymax]
tts_area = tts.area.to_numpy()
trips_grid = burn(tts.geometry, tts["trips_total"] / tts_area * cell_area)
trips_car_grid = burn(tts.geometry, tts["trips_car"] / tts_area * cell_area)
print("TTS zones:", len(tts))


# hex points: keep hexes with >= MIN_RES_FRAC of their area in R zones
# (share measured on the 10m res_mask with a hex-shaped window)

MIN_RES_FRAC = 0.10

dy = HEX_SPACING * np.sqrt(3) / 2
rx0, ry0, rx1, ry1 = res_union.bounds
ys = np.arange(ry0, ry1 + dy, dy)
hx, hy = [], []
for i, y in enumerate(ys):
    xs = np.arange(rx0 + (HEX_SPACING / 2 if i % 2 else 0), rx1 + HEX_SPACING, HEX_SPACING)
    hx.append(xs)
    hy.append(np.full(len(xs), y))
hx, hy = np.concatenate(hx), np.concatenate(hy)
hex_r = HEX_SPACING / np.sqrt(3)  # pointy-top circumradius
kh = int(np.ceil(hex_r / CELL))
ky, kx = np.mgrid[-kh:kh + 1, -kh:kh + 1] * CELL
hex_kernel = ((np.abs(kx) <= HEX_SPACING / 2) & (np.abs(ky) <= hex_r - np.abs(kx) / np.sqrt(3))).astype(float)
res_frac_grid = fftconvolve(res_mask.astype(float), hex_kernel, mode="same") / hex_kernel.sum()

hr, hc = to_rc(hx, hy)
res_frac = res_frac_grid[hr, hc]
keep = res_frac >= MIN_RES_FRAC
hx, hy, hr, hc, res_frac = hx[keep], hy[keep], hr[keep], hc[keep], res_frac[keep]
print("hex points:", len(hx), "| centre in R:", shapely.contains_xy(res_union, hx, hy).sum())


# RADIUS disk window sums, sampled at hex points

k = int(RADIUS // CELL)
yy, xx = np.mgrid[-k:k + 1, -k:k + 1] * CELL
disk = (xx ** 2 + yy ** 2 <= RADIUS ** 2).astype(float)

def window(grid):
    # fft leaves tiny float noise (incl. small negatives) - all inputs are >= 0
    return np.clip(fftconvolve(grid, disk, mode="same")[hr, hc], 0, None)

def ratio(num, den, min_den):
    # null where the window holds too little to measure (noise / ~0 denominators)
    return np.where(den >= min_den, num / np.where(den > 0, den, 1), np.nan)

land_w = window(land)
out = pd.DataFrame({"x": hx, "y": hy})
out["res_frac"] = np.clip(res_frac, 0, 1)
out["land_km2"] = land_w / 1e6
out["kids_5_14"] = window(kids_grid)
out["kids_5_14_km2"] = ratio(out["kids_5_14"], out["land_km2"], 0.01)
out["hh_kids_pct"] = 100 * ratio(window(hh_kids_grid), window(hh_all_grid), 10)
out["income"] = ratio(window(hhinc_grid), window(hh_grid), 10)
out["parcel_n"] = window(parcel_n_grid).round()
out["parcel_mean_m2"] = ratio(window(parcel_area_grid), out["parcel_n"], 5)
out["slope_all_pct"] = ratio(window(sw_grid), window(w_grid), 1000)
out["slope_res_pct"] = ratio(window(sw_res_grid), window(w_res_grid), 1000)
out["street_km"] = window(street_len_grid) / 1000
out["sidewalk_pct"] = 100 * ratio(window(both_len_grid), window(known_len_grid), 100)
out["car_pct"] = 100 * ratio(window(trips_car_grid), window(trips_grid), 10)
print("nulls:", out.isna().sum()[lambda s: s > 0].to_dict())


# output: points + hex cells

out = out.round({
    "res_frac": 3, "land_km2": 3, "kids_5_14": 0, "kids_5_14_km2": 0, "hh_kids_pct": 1, "income": 0,
    "parcel_mean_m2": 1, "slope_all_pct": 2, "slope_res_pct": 2,
    "street_km": 2, "sidewalk_pct": 1, "car_pct": 1,
})

pts = gpd.GeoDataFrame(out, geometry=gpd.points_from_xy(out.x, out.y), crs=CRS).drop(columns=["x", "y"])
pts.to_file("data/hex-metrics-2952.gpkg", driver="GPKG", layer="points")

r = HEX_SPACING / np.sqrt(3)  # pointy-top hex circumradius
ang = np.deg2rad(np.arange(30, 390, 60))
# vertices rounded to cm so neighbouring hexes share identical edges (for topojson arcs)
hexes = [shapely.Polygon(np.round(np.c_[x + r * np.cos(ang), y + r * np.sin(ang)], 2)) for x, y in zip(hx, hy)]
hex_gdf = gpd.GeoDataFrame(out.drop(columns=["x", "y"]), geometry=hexes, crs=CRS)
hex_gdf.to_file("data/hex-metrics-2952.gpkg", driver="GPKG", layer="hexes")


# web: slim hex topojson for the interactive map

WEB_FIELDS = {
    "hh_kids_pct": 1, "kids_5_14_km2": 0, "income": -2, "parcel_mean_m2": 0,
    "slope_res_pct": 1, "sidewalk_pct": 0, "car_pct": 0,
}
web = hex_gdf[list(WEB_FIELDS)].copy()
for c, nd in WEB_FIELDS.items():
    web[c] = web[c].round(nd)
    if nd <= 0:
        web[c] = web[c].astype("Int64")  # nullable, nulls stay null in json
web = gpd.GeoDataFrame(web, geometry=hex_gdf.geometry, crs=CRS).to_crs("EPSG:4326")
web.to_file("local_data/hexes-4326.geojson", driver="GeoJSON")
subprocess.run(
    "geo2topo -q 1e5 hexes=local_data/hexes-4326.geojson > data/hexes.topojson",
    shell=True, check=True,
)

print(out.describe().T)
