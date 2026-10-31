export function percentiles(values) {
	const order = Array.from(values.keys()).filter(i => values[i] != null).sort((a, b) => values[a] - values[b]);
	const out = new Float32Array(values.length).fill(0.5);
	let i = 0;
	while (i < order.length) {
		let j = i;
		while (j + 1 < order.length && values[order[j + 1]] === values[order[i]]) j++;
		const p = (i + j) / 2 / (order.length - 1);
		for (let k = i; k <= j; k++) out[order[k]] = p;
		i = j + 1;
	}
	return out;
}

export function computeScores(pct, weights, dirs, n) {
	const score = new Float32Array(n);
	for (let v = 0; v < weights.length; v++) {
		const w = weights[v];
		if (w < 1e-6) continue;
		const p = pct[v], up = dirs[v] > 0;
		for (let f = 0; f < n; f++) score[f] += w * (up ? p[f] : 1 - p[f]);
	}
	return percentiles(score);
}
