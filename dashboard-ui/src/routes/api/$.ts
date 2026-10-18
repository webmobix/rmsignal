import { createFileRoute } from "@tanstack/react-router";

const HOP_BY_HOP = new Set([
	"connection",
	"keep-alive",
	"proxy-authenticate",
	"proxy-authorization",
	"te",
	"trailer",
	"transfer-encoding",
	"upgrade",
	"host",
]);

/**
 * Resolve the API base per request so it can be supplied by the runtime
 * environment (Cloud Run `--set-env-vars RM_API_URL=...`). Falls back to the
 * local API only outside production.
 */
function apiBase(): string | undefined {
	return (
		process.env.RM_API_URL ??
		(process.env.NODE_ENV === "production"
			? undefined
			: "http://127.0.0.1:8765")
	);
}

/** Forward `/api/**` to the FastAPI service, preserving path, query and body. */
async function proxyApi({ request }: { request: Request }) {
	const baseUrl = apiBase();
	if (!baseUrl) {
		return new Response("RM_API_URL environment variable is not set", {
			status: 500,
		});
	}

	const incoming = new URL(request.url);
	const base = new URL(baseUrl);
	const target = new URL(base);
	target.pathname = `${base.pathname.replace(/\/$/, "")}${incoming.pathname}`;
	target.search = incoming.search;

	const headers = new Headers(request.headers);
	for (const name of HOP_BY_HOP) headers.delete(name);

	const hasBody = request.method !== "GET" && request.method !== "HEAD";
	const upstream = await fetch(target, {
		method: request.method,
		headers,
		body: hasBody ? request.body : undefined,
		redirect: "manual",
		duplex: "half",
	} as RequestInit);

	const responseHeaders = new Headers(upstream.headers);
	for (const name of HOP_BY_HOP) responseHeaders.delete(name);

	return new Response(upstream.body, {
		status: upstream.status,
		statusText: upstream.statusText,
		headers: responseHeaders,
	});
}

export const Route = createFileRoute("/api/$")({
	server: {
		handlers: {
			ANY: proxyApi,
		},
	},
});
