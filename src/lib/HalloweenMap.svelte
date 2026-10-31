<script>
	import { onMount, onDestroy } from "svelte";
	import { base } from "$app/paths";
	import maplibregl from "maplibre-gl";
	import "maplibre-gl/dist/maplibre-gl.css";
	import { feature } from "topojson-client";
	import { VARS, THEMES } from "./config.js";
	import { percentiles, computeScores } from "./scoring.js";
	import { addOverlays } from "./overlays.js";
	import { RecentreControl, NorthArrowControl } from "./controls.js";

	export let weights;
	export let dirs;
	export let theme;

	const BEARING = -17;

	let container;
	let map;
	let mapTheme = null;  // theme of the style currently on the map
	let loaded = false;
	let status = "summoning hexes…";

	let features = [], geo = null, pct = [], scorePct = null;
	let boundaryCoords = [];  // city outline vertices, for framing
	let hoverId = null;  // null = nothing yet, -1 = off the hexes

	// frame the city boundary tightly at the tilted bearing (fitBounds would fit the
	// axis-aligned box, leaving uneven gaps): place the camera, measure the outline's
	// screen extent, then rescale + recentre - exact in one pass at a fixed bearing
	function fitToronto(animate = false) {
		const before = { center: map.getCenter(), zoom: map.getZoom(), bearing: map.getBearing(), padding: map.getPadding() };
		const phone = window.innerWidth <= 700;
		const padding = phone
			? { top: 16, bottom: window.innerHeight * 0.48 + 8, left: 16, right: 16 }
			: { top: 24, bottom: 24, left: 372, right: 24 };

		// phones: the whole city is too small to read, so open on central Toronto instead
		if (phone) {
			const view = { center: [-79.4, 43.715], zoom: 10, bearing: BEARING, padding };
			if (animate) map.easeTo({ ...view, duration: 800 });
			else map.jumpTo(view);
			return;
		}

		const el = map.getContainer();
		const w = el.clientWidth - padding.left - padding.right;
		const h = el.clientHeight - padding.top - padding.bottom;

		map.jumpTo({ center: [-79.38, 43.71], zoom: 10, bearing: BEARING, padding: { top: 0, bottom: 0, left: 0, right: 0 } });
		let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
		for (const c of boundaryCoords) {
			const p = map.project(c);
			x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x);
			y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y);
		}
		const zoom = 10 + Math.log2(Math.min(w / (x1 - x0), h / (y1 - y0)));
		const center = map.unproject([(x0 + x1) / 2, (y0 + y1) / 2]);
		if (animate) {
			// measuring moved the camera; restore it (same frame, no flicker) and glide instead
			map.jumpTo(before);
			map.easeTo({ center, zoom, bearing: BEARING, padding, duration: 800 });
		} else {
			map.jumpTo({ center, zoom, bearing: BEARING, padding });
		}
	}

	// OSM shortbread vector tiles, light / dark versions of the libraries-by-transit tour style
	const styleCache = {};
	async function getStyle(name) {
		if (!styleCache[name]) styleCache[name] = await fetch(`${base}/${THEMES[name].style}`).then(r => r.json());
		return styleCache[name];
	}

	let updateQueued = false;
	function scheduleUpdate() {
		if (updateQueued || !map || !map.getSource("hexes")) return;
		updateQueued = true;
		requestAnimationFrame(() => {
			updateQueued = false;
			scorePct = computeScores(pct, weights, dirs, features.length);
			for (let f = 0; f < features.length; f++) {
				map.setFeatureState({ source: "hexes", id: f }, { s: scorePct[f] });
			}
		});
	}

	async function setMapTheme(name) {
		if (!loaded || name === mapTheme) return;
		mapTheme = name;
		const style = await getStyle(name);
		map.setStyle(style, { diff: false });
		map.once("style.load", () => {
			addOverlays(map, THEMES[name], geo, base);
			hoverId = null;
			scheduleUpdate();
		});
	}

	$: weights, dirs, scheduleUpdate();
	$: setMapTheme(theme);

	// refit only when crossing the phone / desktop layout breakpoint
	let wasPhone;
	function onResize() {
		const phone = window.innerWidth <= 700;
		if (map && phone !== wasPhone) { wasPhone = phone; fitToronto(); }
	}

	onMount(() => {
		wasPhone = window.innerWidth <= 700;
		// the page sets `theme` after this mounts, so read the saved one directly
		const initialTheme = THEMES[document.documentElement.dataset.theme] ? document.documentElement.dataset.theme : "dark";

		Promise.all([
			getStyle(initialTheme),
			fetch(`${base}/data/hexes-200.topojson`).then(r => r.json()),
			fetch(`${base}/data/toronto-boundary.geojson`).then(r => r.json()),
		]).then(([style, topo, boundary]) => {
			boundaryCoords = boundary.features.flatMap(f =>
				f.geometry.type === "Polygon" ? f.geometry.coordinates[0] : f.geometry.coordinates.flatMap(p => p[0]));
			geo = feature(topo, topo.objects.hexes);
			features = geo.features;
			features.forEach((f, i) => { f.id = i; });
			pct = VARS.map(v => percentiles(features.map(f => f.properties[v.key])));

			mapTheme = initialTheme;
			map = new maplibregl.Map({
				container,
				style,
				center: [-79.386783, 43.700203],
				zoom: 10,
				minZoom: 8,  // phones need < 9 to frame the whole city
				maxZoom: 17,
				bearing: BEARING,
				dragRotate: false,
				touchPitch: false,
				attributionControl: false,  // credited in the panel note
			});
			map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
			map.addControl(new RecentreControl(() => fitToronto(true)), "top-right");
			map.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: "metric" }), "bottom-right");
			map.addControl(new NorthArrowControl(), "bottom-right");  // added after, so it stacks above the scale

			map.on("load", () => {
				addOverlays(map, THEMES[mapTheme], geo, base);
				fitToronto();
				scheduleUpdate();
				status = null;
				loaded = true;
				// the theme may have been toggled while loading
				setMapTheme(theme);
			});

			// ---------- hover ----------

			const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, maxWidth: "260px" });

			function setHover(id) {
				const src = map.getSource("hover");
				if (src) src.setData({ type: "FeatureCollection", features: id >= 0 ? [features[id]] : [] });
				hoverId = id;
			}

			map.on("mousemove", e => {
				if (!map.getLayer("hex-fill")) return;
				const f = map.queryRenderedFeatures(e.point, { layers: ["hex-fill"] })[0];
				const id = f ? f.id : -1;
				popup.setLngLat(e.lngLat);
				if (id === hoverId) return;  // same hex (or still off-hex): just move the card
				setHover(id);
				if (!f) {
					map.getCanvas().style.cursor = "";
					popup.setHTML(`<div class="pop-empty">Not residential or no data</div>`).addTo(map);
					return;
				}
				map.getCanvas().style.cursor = "pointer";
				const s = scorePct ? scorePct[f.id] : 0;
				const rows = VARS.map((v, i) => {
					const val = f.properties[v.key];
					const missing = val == null;
					const p = dirs[i] > 0 ? pct[i][f.id] : 1 - pct[i][f.id];
					return `<div class="pop-row" style="opacity:${weights[i] < 0.005 ? 0.4 : 1}">
						<span>${v.label}</span><span class="pop-val">${missing ? "no data" : v.fmt(val)}</span>
						<div class="pop-bar"><span style="width:${missing ? 0 : Math.round(p * 100)}%"></span></div></div>`;
				}).join("");
				// upper half reads "Top X%", lower half "Bottom X%" (clearer than "Top 98%")
				const rank = s >= 0.5 ? `Top ${Math.max(1, Math.round((1 - s) * 100))}%` : `Bottom ${Math.max(1, Math.round(s * 100))}%`;
				popup.setHTML(`<div class="pop-score">${rank}</div>${rows}`).addTo(map);
			});
			map.getCanvas().addEventListener("mouseleave", () => {
				setHover(-1);
				hoverId = null;
				popup.remove();
			});
		}).catch(err => {
			status = "the ghosts ate the data (see console)";
			console.error(err);
		});
	});

	onDestroy(() => { if (map) map.remove(); });
</script>

<svelte:window on:resize={onResize} />

<div id="map" bind:this={container}></div>
{#if status}
	<div id="loading">{status}</div>
{/if}

<style>
	#map { position: absolute; inset: 0; }

	/* vignette */
	#map::after {
		content: ""; position: absolute; inset: 0; pointer-events: none; z-index: 1;
		background: radial-gradient(ellipse at 55% 50%, transparent 55%, var(--vignette) 100%);
	}

	#loading {
		position: absolute; inset: 0; display: grid; place-items: center; z-index: 3;
		font-family: Creepster, cursive; font-size: 28px; color: var(--pumpkin); background: var(--bg);
	}

	/* popup + controls are built by maplibre, outside this component's markup */
	:global(.maplibregl-popup-content) {
		background: var(--popup); color: var(--text); border: 1px solid var(--line); border-radius: 0;
		padding: 10px 12px; font-family: "Open Sans", sans-serif; font-size: 12px; min-width: 210px;
	}
	:global(.maplibregl-popup-tip) { border-top-color: var(--popup) !important; border-bottom-color: var(--popup) !important; }
	:global(.pop-score) { font-family: Creepster, cursive; font-size: 20px; color: var(--accent); margin-bottom: 6px; }
	:global(.pop-empty) { color: var(--muted); }
	:global(.maplibregl-popup-content:has(.pop-empty)) { min-width: 0; }
	:global(.pop-row) { display: grid; grid-template-columns: 1fr auto; gap: 2px 10px; margin: 3px 0; }
	:global(.pop-val) { font-variant-numeric: tabular-nums; text-align: right; }
	:global(.pop-bar) { grid-column: 1 / -1; height: 3px; background: var(--track); border-radius: 0; }
	:global(.pop-bar span) { display: block; height: 100%; border-radius: 0; background: var(--pumpkin); }
	/* zoom buttons follow the theme */
	:global(.maplibregl-ctrl-group) { background: var(--panel); border: 1px solid var(--line); box-shadow: none !important; border-radius: 0 !important; }
	:global(.maplibregl-ctrl-group button) { border-radius: 0 !important; }
	:global(.maplibregl-ctrl-group button.recentre) { display: grid; place-items: center; color: var(--text); }
	:global(.north-arrow) { color: var(--text); opacity: 0.7; width: 29px; display: grid; place-items: center; pointer-events: none; }
	:global(.north-arrow svg) { transform-origin: 50% 60%; }
	:global(.maplibregl-ctrl.maplibregl-ctrl-scale) {
		background: var(--panel); color: var(--muted); border: 1px solid var(--muted); border-top: none;
		border-radius: 0; font-family: "Open Sans", sans-serif; font-size: 10px; padding: 0 4px;
	}
	:global(.maplibregl-ctrl-group button + button) { border-top-color: var(--line); }
	:global(.maplibregl-ctrl-group button:not(:disabled):hover) { background-color: var(--chip); }
	:global(:root[data-theme="dark"] .maplibregl-ctrl-group .maplibregl-ctrl-icon) { filter: invert(1) opacity(0.8); }
</style>
