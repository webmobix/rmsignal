import type { components } from "./schema";

export type Schemas = components["schemas"];

export class ApiError extends Error {
	readonly status: number;
	readonly detail: string;
	constructor(status: number, detail: string) {
		super(`API ${status}: ${detail}`);
		this.name = "ApiError";
		this.status = status;
		this.detail = detail;
	}
}

export type Params = Record<
	string,
	string | number | boolean | null | undefined
>;

const BASE = (import.meta.env?.VITE_API_BASE as string | undefined) ?? "";

/** Build `/api/...?as_of=...&k=v`; undefined and null params are dropped. */
export function buildUrl(
	path: string,
	params: Params = {},
	asOf?: string | null,
): string {
	const query = new URLSearchParams();
	if (asOf) query.set("as_of", asOf);
	for (const [key, value] of Object.entries(params)) {
		if (value !== undefined && value !== null) query.set(key, String(value));
	}
	const qs = query.toString();
	return `${BASE}/api${path}${qs ? `?${qs}` : ""}`;
}

async function errorDetail(response: Response): Promise<string> {
	try {
		const body = await response.json();
		const detail = body?.detail;
		if (typeof detail === "string") return detail;
		if (detail) return JSON.stringify(detail);
	} catch {
		// non-JSON body: fall through to the status text
	}
	return response.statusText || "request failed";
}

export async function apiGet<T>(
	path: string,
	params: Params = {},
	asOf?: string | null,
	signal?: AbortSignal,
): Promise<T> {
	let response: Response;
	try {
		response = await fetch(buildUrl(path, params, asOf), { signal });
	} catch (error) {
		if (error instanceof DOMException && error.name === "AbortError")
			throw error;
		throw new ApiError(0, "the API is not reachable");
	}
	if (!response.ok)
		throw new ApiError(response.status, await errorDetail(response));
	return (await response.json()) as T;
}
