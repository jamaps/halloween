import { redirect } from "@sveltejs/kit";
import { base } from "$app/paths";

// the map is the only page for now; prerendering writes this as a meta-refresh redirect
export function load() {
	redirect(307, `${base}/toronto-map`);
}
