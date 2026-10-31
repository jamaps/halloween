// variables: key, label, description, default direction (+1 more is better, -1 less is better)
export const VARS = [
	{ key: "kids_5_14_km2", group: "Demographics", label: "Kid density", desc: "More kids per km² (more fun? more competition?)", dir: 1, fmt: v => `${Math.round(v)}/km²` },
	{ key: "hh_kids_pct", group: "Demographics", label: "Family households", desc: "% of households with children (more decorations?)", dir: 1, fmt: v => `${v.toFixed(1)}%` },
	{ key: "income", group: "Demographics", label: "Household income", desc: "More full-size bars?", dir: 1, fmt: v => `$${(v / 1000).toFixed(0)}k` },
	{ key: "parcel_mean_m2", group: "Geography", label: "Small lots", desc: "Smaller lots = more doors per minute?", dir: -1, fmt: v => `${Math.round(v)} m²` },
	{ key: "slope_res_pct", group: "Geography", label: "Flat terrain", desc: "Fewer hills = less tired legs?", dir: -1, fmt: v => `${v.toFixed(1)}% slope` },
	{ key: "sidewalk_pct", group: "Traffic safety", label: "Sidewalks", desc: "More streets with sidewalks on both sides", dir: 1, fmt: v => `${Math.round(v)}%` },
	{ key: "car_pct", group: "Traffic safety", label: "Car trips", desc: "% of local residents' trips by car (fewer cars = safer streets)", dir: -1, fmt: v => `${Math.round(v)}%` },
];

// per-theme map style, score ramp + overlay colours.
// best hexes get the colour that contrasts most with the basemap:
// dark = purple -> blood red -> pumpkin -> candle; light = flipped, cream -> pumpkin -> deep purple
export const THEMES = {
	dark: {
		style: "map-style-dark.json", icon: "🕯️",
		ramp: [
			[0.0, "#34204f"], [0.28, "#4a1c5e"], [0.5, "#7d2052"],
			[0.7, "#c2410c"], [0.82, "#f97316"], [0.9, "#fbbf24"], [1.0, "#fde68a"],
		],
		opacity: [0, 0.55, 0.9, 0.8, 1, 0.92],
		mask: "#0b0910", hover: "#fde68a", rail: "#4a4258", lake: "#8792ab", city: "#9a8fab",
		label: "#f5f0fb", labelHalo: "#0b0910",
	},
	light: {
		style: "map-style-light.json", icon: "🦇",
		ramp: [
			[0.0, "#fbe8c8"], [0.28, "#f9c784"], [0.5, "#f59e0b"],
			[0.7, "#ea580c"], [0.82, "#b91c1c"], [0.9, "#6b1d5e"], [1.0, "#2e1747"],
		],
		opacity: [0, 0.6, 0.9, 0.85, 1, 0.92],
		mask: "#f6f4ef", hover: "#65a30d", rail: "#b7b0bf", lake: "#6f8fa0", city: "#7d7488",
		label: "#2a2035", labelHalo: "#ffffff",
	},
};

// starting weights (relative; normalised to sum to 1, so displayed % match after rounding)
export const DEFAULT_WEIGHTS = {
	kids_5_14_km2: 7, hh_kids_pct: 7, income: 2,
	parcel_mean_m2: 10, slope_res_pct: 25,
	sidewalk_pct: 30, car_pct: 20,
};
