// our layers on top of the basemap style - re-added after every theme (style) switch.
// `base` is the SvelteKit base path, prefixed onto the static data files
export function addOverlays(map, t, geo, base) {
	// hexes go under streets and labels so streets read through.
	// cut tiles only up to z12 (overzoomed beyond; ~2m precision) - keeps the worker
	// and GPU memory light enough that tiles don't drop out when zooming
	map.addSource("hexes", { type: "geojson", data: geo, maxzoom: 12, buffer: 16 });
	map.addLayer({
		id: "hex-fill",
		type: "fill",
		source: "hexes",
		paint: {
			"fill-antialias": false,  // no hairline seams between hexes
			"fill-color": ["interpolate", ["linear"], ["coalesce", ["feature-state", "s"], 0], ...t.ramp.flat()],
			"fill-opacity": ["interpolate", ["linear"], ["coalesce", ["feature-state", "s"], 0], ...t.opacity],
		},
	}, "cycleways");

	// main + branch rail lines and surface light rail (OSM usage=main|branch via Overpass; no yards)
	map.addSource("rail", { type: "geojson", data: `${base}/data/rail-main.geojson` });
	map.addLayer({
		id: "rail", type: "line", source: "rail",
		paint: {
			"line-color": t.rail,
			"line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.6, 15, 1.6],
			"line-dasharray": [4, 2],
		},
	}, "cycleways");

	// hovered hex lives in its own one-feature source, so hovering never touches the hex layer
	map.addSource("hover", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
	map.addLayer({ id: "hex-hover", type: "line", source: "hover", paint: { "line-color": t.hover, "line-width": 2 } });

	// inverted mask over everything outside the City of Toronto, plus a faint glowing edge
	map.addSource("mask", { type: "geojson", data: `${base}/data/toronto-mask.geojson` });
	map.addLayer({ id: "mask", type: "fill", source: "mask", paint: { "fill-color": t.mask, "fill-opacity": 0.92 } });
	map.addSource("boundary", { type: "geojson", data: `${base}/data/toronto-boundary.geojson` });
	map.addLayer({
		id: "boundary-glow", type: "line", source: "boundary",
		paint: { "line-color": "#f97316", "line-width": 6, "line-blur": 6, "line-opacity": 0.25 },
	});
	map.addLayer({
		id: "boundary", type: "line", source: "boundary",
		paint: { "line-color": "#f97316", "line-width": 1, "line-opacity": 0.6 },
	});

	// City neighbourhood names (labelled at each neighbourhood's pole of inaccessibility)
	map.addSource("nbhd", { type: "geojson", data: `${base}/data/neighbourhood-labels.geojson` });
	map.addLayer({
		id: "nbhd-labels",
		type: "symbol",
		source: "nbhd",
		minzoom: 10.5,
		layout: {
			"text-field": ["get", "name"],
			"text-font": ["Open Sans Italic"],
			"text-size": ["interpolate", ["linear"], ["zoom"], 10.5, 9, 14, 13],
			"text-max-width": 8,
			"text-letter-spacing": 0.03,
			"text-padding": 6,
		},
		paint: {
			"text-color": t.label,
			"text-halo-color": t.labelHalo,
			"text-halo-width": 2,
			"text-opacity": 0.88,
		},
	});

	// faint context labels above the mask: the lake and neighbouring cities,
	// all sitting outside the city boundary
	const place = (name, kind, coordinates) => ({ type: "Feature", properties: { name, kind }, geometry: { type: "Point", coordinates } });
	map.addSource("context", {
		type: "geojson",
		data: {
			type: "FeatureCollection",
			features: [
				place("Lake Ontario", "water", [-79.21, 43.665]),
				place("Mississauga", "city", [-79.62, 43.6]),
				place("Brampton", "city", [-79.69, 43.77]),
				place("Vaughan", "city", [-79.53, 43.83]),
				place("Richmond Hill", "city", [-79.43, 43.87]),
				place("Markham", "city", [-79.3, 43.87]),
				place("Pickering", "city", [-79.08, 43.83]),
			],
		},
	});
	const contextLayout = {
		"text-field": ["get", "name"],
		"text-size": ["interpolate", ["linear"], ["zoom"], 9, 11, 13, 16],
		"text-allow-overlap": true,
		"text-ignore-placement": true,
	};
	map.addLayer({
		id: "lake-label", type: "symbol", source: "context", filter: ["==", ["get", "kind"], "water"],
		layout: { ...contextLayout, "text-font": ["Open Sans Italic"], "text-letter-spacing": 0.15 },
		paint: { "text-color": t.lake, "text-opacity": 0.6 },
	});
	map.addLayer({
		id: "city-labels", type: "symbol", source: "context", filter: ["==", ["get", "kind"], "city"],
		// same type as the neighbourhood labels, in a fainter colour
		layout: {
			...contextLayout, "text-font": ["Open Sans Italic"], "text-letter-spacing": 0.03,
			"text-size": ["interpolate", ["linear"], ["zoom"], 10.5, 9, 14, 13],
		},
		paint: { "text-color": t.city, "text-halo-color": t.labelHalo, "text-halo-width": 2, "text-opacity": 0.8 },
	});
}
