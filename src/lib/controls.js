// "re-centre on Toronto" button, styled like the zoom buttons and stacked under them
export class RecentreControl {
	constructor(onClick) { this.onClick = onClick; }
	onAdd() {
		this.el = document.createElement("div");
		this.el.className = "maplibregl-ctrl maplibregl-ctrl-group";
		this.el.innerHTML = `<button type="button" class="recentre" title="Re-centre on Toronto" aria-label="Re-centre on Toronto">
			<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square">
				<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/><circle cx="12" cy="12" r="2"/>
			</svg></button>`;
		this.el.querySelector("button").addEventListener("click", this.onClick);
		return this.el;
	}
	onRemove() { this.el.remove(); }
}

// small north arrow, tilted with the map so it points to true north
export class NorthArrowControl {
	onAdd(m) {
		this.map = m;
		this.el = document.createElement("div");
		this.el.className = "maplibregl-ctrl north-arrow";
		this.el.title = "North";
		this.el.innerHTML = `<svg viewBox="0 0 24 32" width="18" height="24" fill="currentColor">
			<text x="12" y="9" text-anchor="middle" font-size="9" font-family="Open Sans, sans-serif" font-weight="600">N</text>
			<path d="M12 12 L17 30 L12 26 L7 30 Z"/></svg>`;
		this.update = () => { this.el.firstChild.style.transform = `rotate(${-m.getBearing()}deg)`; };
		m.on("rotate", this.update);
		this.update();
		return this.el;
	}
	onRemove() { this.map.off("rotate", this.update); this.el.remove(); }
}
