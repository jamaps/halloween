<script>
	import { onMount } from "svelte";
	import "../../app.css";
	import HalloweenMap from "$lib/HalloweenMap.svelte";
	import { VARS, THEMES, DEFAULT_WEIGHTS } from "$lib/config.js";

	const defaultTotal = VARS.reduce((a, v) => a + DEFAULT_WEIGHTS[v.key], 0);
	let weights = VARS.map(v => DEFAULT_WEIGHTS[v.key] / defaultTotal);

	let theme = "dark";
	onMount(() => {
		const t = document.documentElement.dataset.theme;
		if (THEMES[t]) theme = t;
	});

	function toggleTheme() {
		theme = theme === "dark" ? "light" : "dark";
		document.documentElement.dataset.theme = theme;
		try { localStorage.setItem("tot-theme", theme); } catch (e) {}
	}

	function setWeight(i, v) {
		const othersSum = 1 - weights[i];
		const target = 1 - v;
		weights = weights.map((w, j) => {
			if (j === i) return v;
			return othersSum > 1e-9 ? w * target / othersSum : target / (VARS.length - 1);
		});
	}

	function thumbClass(pctW) {
		if (pctW === 0) return "off";
		if (pctW >= 75) return "ogre";
		if (pctW >= 50) return "goblin";
		if (pctW >= 25) return "zombie";
		return "";
	}

	$: rampBackground = `linear-gradient(to right, ${THEMES[theme].ramp.map(([t, c]) => `${c} ${t * 100}%`).join(", ")})`;
</script>

<svelte:head>
	<title>Where to Trick or Treat in Toronto?</title>
	<meta name="description" content="Pick what matters to you (flat streets, demographics, sidewalks, etc.) and see which residential parts of Toronto come out on top." />
	<link rel="canonical" href="https://jamaps.github.io/halloween/toronto-map" />
	<meta property="og:type" content="website" />
	<meta property="og:url" content="https://jamaps.github.io/halloween/toronto-map" />
	<meta property="og:title" content="Where to Trick or Treat in Toronto?" />
	<meta property="og:description" content="Pick what matters to you (flat streets, demographics, sidewalks, etc.) and see which residential parts of Toronto come out on top." />
	<meta property="og:image" content="https://jamaps.github.io/halloween/toronto-map-card.png" />
	<meta property="og:image:width" content="1912" />
	<meta property="og:image:height" content="961" />
	<meta property="og:image:alt" content="Map of Toronto with residential areas shaded from purple to bright yellow by trick-or-treating score" />
	<meta name="twitter:card" content="summary_large_image" />
	<link rel="preconnect" href="https://fonts.googleapis.com">
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous">
	<link href="https://fonts.googleapis.com/css2?family=Creepster&family=Open+Sans:wght@400;600;700&display=swap" rel="stylesheet">
</svelte:head>

<HalloweenMap {weights} {theme} />

<div id="panel">
	<div class="title-row">
		<h1>Where to Trick or Treat in Toronto?</h1>
		<button id="theme-toggle" title="light a candle / release the bats" on:click={toggleTheme}>{THEMES[theme].icon}</button>
	</div>
	<p class="sub">Select what matters to you. Slide right to make something matter more. The sliders always add up to 100%, so you'll have to make a few tradeoffs.</p>
	<p class="byline">Built by Jeff Allen. Updated October 31, 2026</p>

	<div class="legend">
		<div class="ramp" style:background={rampBackground}></div>
		<div class="ramp-labels"><span>meh</span><span>better</span><span>great!</span></div>
	</div>

	{#each VARS as v, i}
		{@const pctW = Math.round(weights[i] * 100)}
		{#if i === 0 || VARS[i - 1].group !== v.group}
			<h2 class="group">{v.group}</h2>
		{/if}
		<div class="var">
			<div class="var-head">
				<span class="var-name">{v.label}</span>
				<span class="var-weight">{pctW}%</span>
			</div>
			<div class="var-desc" id="desc-{v.key}">{v.desc}</div>
			<input
				type="range" min="0" max="100" step="1"
				class={thumbClass(pctW)}
				style:--p="{pctW}%"
				value={pctW}
				aria-label={v.label}
				aria-describedby="desc-{v.key}"
				aria-valuetext="{pctW}%"
				on:input={e => setWeight(i, e.currentTarget.value / 100)}
			>
		</div>
	{/each}

	<p class="note">
		This is a just-for-fun Halloween map, so please don't take it too seriously. Every neighbourhood has its own tricks and treats that aren't captured by this data. 👻
		<br><br>
		Each hex averages data in the area within 500m of it, about a 10-minute walk. The hexes cover residential zones only (R, RD, RS, RT, RM, RA, RAC in current or 2014 zoning). Colour = percentile of the weighted score.
		<br><br>
		Data sources: Statistics Canada (2021 Census of Population, dissemination areas);
		City of Toronto Open Data (zoning by-law, property boundaries, neighbourhoods, pedestrian network, 2023 TIN);
		Transportation Tomorrow Survey 2022; basemap and labels © OpenStreetMap contributors.
		<br><br>
		Data and details are on <a href="https://github.com/jamaps/halloween" target="_blank" rel="noopener">GitHub</a>.
	</p>
</div>

<style>
	#panel {
		position: absolute; top: 16px; left: 16px; bottom: 16px; width: 340px; z-index: 2;
		background: var(--panel); border: 1px solid var(--panel-border);
		backdrop-filter: blur(6px); overflow-y: auto; padding: 18px 18px 14px;
		box-shadow: 0 0 40px var(--panel-glow);
		scrollbar-width: thin;
		scrollbar-color: var(--line) transparent;
	}
	#panel:hover { scrollbar-color: color-mix(in srgb, var(--muted) 80%, transparent) transparent; }
	#panel::-webkit-scrollbar { width: 6px; }
	#panel::-webkit-scrollbar-track { background: transparent; }
	#panel::-webkit-scrollbar-thumb { background: var(--line); }
	#panel::-webkit-scrollbar-thumb:hover { background: var(--pumpkin); }
	.title-row { display: flex; align-items: flex-start; gap: 10px; }
	h1 {
		flex: 1; font-family: Creepster, cursive; font-weight: 400; font-size: 32px; line-height: 1;
		margin: 0 0 6px; color: var(--pumpkin); letter-spacing: 1px;
		text-shadow: 0 0 14px var(--title-glow);
	}
	#theme-toggle {
		flex: none; width: 34px; height: 34px; border-radius: 0; cursor: pointer;
		background: var(--chip); border: 1px solid var(--line); font-size: 16px; line-height: 1;
	}
	#theme-toggle:hover { border-color: var(--pumpkin); }
	.sub { color: var(--muted); margin: 0 0 4px; line-height: 1.45; font-size: 13px; }
	.byline { color: var(--muted); font-size: 10px; font-style: italic; margin: 0 0 14px; }

	.var { padding: 9px 0 7px; border-top: 1px dashed var(--line); }
	h2.group {
		margin: 13px 0 0; padding-top: 11px; border-top: 1px solid var(--line);
		font-size: 13px; font-weight: 700; font-style: italic; color: var(--accent);
		text-decoration: underline; text-underline-offset: 3px;
	}
	h2.group + .var { border-top: none; padding-top: 9px; }
	.var-head { display: flex; align-items: baseline; gap: 8px; font-size: 13px; }
	.var-name { font-weight: 700; flex: 1; }
	.var-weight { font-variant-numeric: tabular-nums; color: var(--accent); font-weight: 600; min-width: 38px; text-align: right; }
	.var-desc { color: var(--muted); font-size: 11px; margin: 1px 0 5px; }

	input[type=range] {
		-webkit-appearance: none; appearance: none; width: 100%; height: 22px; margin: 0;
		background: transparent; cursor: pointer;
		--thumb: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎃</text></svg>");
	}
	input[type=range].off { --thumb: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>☠️</text></svg>"); }
	input[type=range].zombie { --thumb: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🧟</text></svg>"); }
	input[type=range].goblin { --thumb: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>👺</text></svg>"); }
	input[type=range].ogre { --thumb: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>👹</text></svg>"); }
	input[type=range]::-webkit-slider-runnable-track {
		height: 3px; border-radius: 0;
		background: linear-gradient(to right, var(--slider) var(--p), color-mix(in srgb, var(--slider) 25%, transparent) var(--p));
	}
	input[type=range]::-moz-range-track {
		height: 3px; border-radius: 0;
		background: linear-gradient(to right, var(--slider) var(--p), color-mix(in srgb, var(--slider) 25%, transparent) var(--p));
	}
	input[type=range]::-webkit-slider-thumb {
		-webkit-appearance: none; appearance: none; width: 22px; height: 22px; margin-top: -9.5px;
		border: none; background: transparent center / contain no-repeat var(--thumb);
	}
	input[type=range]::-moz-range-thumb {
		width: 22px; height: 22px; border: none; background: transparent center / contain no-repeat var(--thumb);
	}

	.legend { margin: 0 0 2px; }
	.ramp { height: 10px; }
	.ramp-labels { display: flex; justify-content: space-between; color: var(--muted); font-size: 11px; margin-top: 4px; }
	.note { color: var(--muted); font-size: 11px; line-height: 1.5; margin: 4px 0 0; padding-top: 12px; border-top: 1px solid var(--line); }
	.note a { color: var(--muted); }
	.note a:hover { color: var(--pumpkin); }

	@media (max-width: 700px) {
		#panel { top: auto; left: 8px; right: 8px; bottom: 8px; width: auto; max-height: 48vh; padding: 14px; }
		h1 { font-size: 26px; }
	}
</style>
