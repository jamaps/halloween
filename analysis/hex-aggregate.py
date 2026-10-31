# Aggregate the 100m hex points (from hex-metrics.py) up to a coarser hex grid
# for the web map - each coarse hex gets the mean of the 100m points inside it.

import subprocess
import sys
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

CRS = "EPSG:2952"
SPACING = int(sys.argv[1]) if len(sys.argv) > 1 else 200  # m between neighbouring hex centres

WEB_FIELDS = {
    "hh_kids_pct": 1, "kids_5_14_km2": 0, "income": -2, "parcel_mean_m2": 0,
    "slope_res_pct": 1, "sidewalk_pct": 0, "car_pct": 0,
}

pts = gpd.read_file("data/hex-metrics-2952.gpkg", layer="points")
x, y = pts.geometry.x.to_numpy(), pts.geometry.y.to_numpy()

# pointy-top hex lattice: point -> axial coords -> cube rounding -> nearest centre
r = SPACING / np.sqrt(3)  # circumradius
x0, y0 = np.floor(x.min()), np.floor(y.min())
q = (np.sqrt(3) / 3 * (x - x0) - (y - y0) / 3) / r
s = (2 / 3 * (y - y0)) / r
cx, cz = q, s
cy = -cx - cz
rx, ry, rz = np.round(cx), np.round(cy), np.round(cz)
dx, dy, dz = np.abs(rx - cx), np.abs(ry - cy), np.abs(rz - cz)
fix_x = (dx > dy) & (dx > dz)
fix_y = ~fix_x & (dy > dz)
rx = np.where(fix_x, -ry - rz, rx)
rz = np.where(~fix_x & ~fix_y, -rx - ry, rz)
pts["hq"], pts["hr"] = rx.astype(int), rz.astype(int)

agg = pts.drop(columns="geometry").groupby(["hq", "hr"])[list(WEB_FIELDS)].mean()
agg["n_100m"] = pts.groupby(["hq", "hr"]).size()
agg = agg.reset_index()
agg["filled"] = False


# fill gaps, each filled hex = mean of its present neighbours
#   1. enclosed holes of <= MAX_HOLE hexes (filled from the edges inward)
#   2. then any missing hex with >= MIN_NEIGHBOURS of 6 neighbours present (one pass)

warnings.filterwarnings("ignore", "Mean of empty slice")  # all neighbours null -> stays null

MAX_HOLE = 4
MIN_NEIGHBOURS = 5
NEIGHBOURS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]

vals = {(q_, r_): row for q_, r_, row in zip(agg["hq"], agg["hr"], agg[list(WEB_FIELDS)].to_dict("records"))}

def neighbour_mean(cell):
    nbrs = [vals[(cell[0] + dq, cell[1] + dr)] for dq, dr in NEIGHBOURS if (cell[0] + dq, cell[1] + dr) in vals]
    return {c: np.nanmean([n[c] for n in nbrs]) for c in WEB_FIELDS}, len(nbrs)

# 1. enclosed holes: flood-fill missing cells inside the (padded) lattice bbox;
#    components touching the bbox edge are outside, not holes
q_lo, q_hi = agg["hq"].min() - 1, agg["hq"].max() + 1
r_lo, r_hi = agg["hr"].min() - 1, agg["hr"].max() + 1
seen = set()
holes = []
for q_ in range(q_lo, q_hi + 1):
    for r_ in range(r_lo, r_hi + 1):
        if (q_, r_) in vals or (q_, r_) in seen:
            continue
        comp, stack, edge = [], [(q_, r_)], False
        seen.add((q_, r_))
        while stack:
            cq, cr = stack.pop()
            comp.append((cq, cr))
            if cq in (q_lo, q_hi) or cr in (r_lo, r_hi):
                edge = True
            for dq, dr in NEIGHBOURS:
                n = (cq + dq, cr + dr)
                if q_lo <= n[0] <= q_hi and r_lo <= n[1] <= r_hi and n not in vals and n not in seen:
                    seen.add(n)
                    stack.append(n)
        if not edge and len(comp) <= MAX_HOLE:
            holes.append(comp)

hole_filled = []
for comp in holes:
    todo = set(comp)
    while todo:
        best = max(todo, key=lambda c: neighbour_mean(c)[1])
        vals[best] = neighbour_mean(best)[0]
        hole_filled.append(best)
        todo.remove(best)
print("holes <=", MAX_HOLE, "hexes:", len(holes), "| hexes filled:", len(hole_filled))

# 2. missing hexes with enough neighbours (based on hexes present after step 1)
cand = {(q_ + dq, r_ + dr) for q_, r_ in vals for dq, dr in NEIGHBOURS} - set(vals)
nbr_filled = {c: neighbour_mean(c) for c in cand}
nbr_filled = {c: m for c, (m, n) in nbr_filled.items() if n >= MIN_NEIGHBOURS}
vals.update(nbr_filled)
print(">=", MIN_NEIGHBOURS, "neighbours filled:", len(nbr_filled))

new = [{"hq": c[0], "hr": c[1], **vals[c], "n_100m": 0, "filled": True} for c in hole_filled + list(nbr_filled)]
agg = pd.concat([agg, pd.DataFrame(new)], ignore_index=True)

hcx = x0 + r * (np.sqrt(3) * agg["hq"] + np.sqrt(3) / 2 * agg["hr"])
hcy = y0 + r * 1.5 * agg["hr"]
ang = np.deg2rad(np.arange(30, 390, 60))
hexes = [shapely.Polygon(np.round(np.c_[cx_ + r * np.cos(ang), cy_ + r * np.sin(ang)], 2)) for cx_, cy_ in zip(hcx, hcy)]

for c, nd in WEB_FIELDS.items():
    agg[c] = agg[c].round(nd)
    if nd <= 0:
        agg[c] = agg[c].astype("Int64")  # nullable, nulls stay null in json

out = gpd.GeoDataFrame(agg[list(WEB_FIELDS)], geometry=hexes, crs=CRS)
gpd.GeoDataFrame(agg.drop(columns=["hq", "hr"]), geometry=hexes, crs=CRS).to_file(
    "data/hex-metrics-2952.gpkg", driver="GPKG", layer=f"hexes_{SPACING}m",
)
out.to_crs("EPSG:4326").to_file(f"local_data/hexes-{SPACING}-4326.geojson", driver="GeoJSON")
subprocess.run(
    f"geo2topo -q 1e5 hexes=local_data/hexes-{SPACING}-4326.geojson > ../static/data/hexes-{SPACING}.topojson",
    shell=True, check=True,
)
print(f"{len(pts)} points -> {len(out)} hexes at {SPACING}m; points per hex:", agg["n_100m"].describe().round(1).to_dict())
