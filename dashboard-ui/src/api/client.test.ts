import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet, buildUrl } from "./client";

afterEach(() => vi.restoreAllMocks());

describe("buildUrl", () => {
	it("prefixes /api and injects as_of first", () => {
		expect(buildUrl("/overview", {}, "2026-08-26")).toBe(
			"/api/overview?as_of=2026-08-26",
		);
	});
	it("drops undefined and null params and keeps the rest", () => {
		expect(buildUrl("/x", { a: 1, b: undefined, c: null, d: "z" })).toBe(
			"/api/x?a=1&d=z",
		);
	});
	it("has no query string when empty", () => {
		expect(buildUrl("/as-of")).toBe("/api/as-of");
	});
});

describe("apiGet", () => {
	it("returns parsed JSON", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn(async () => new Response(JSON.stringify({ ok: 1 }))),
		);
		await expect(apiGet("/rm", {}, "2026-08-26")).resolves.toEqual({ ok: 1 });
	});
	it("maps an error body to ApiError with detail", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn(
				async () =>
					new Response(JSON.stringify({ detail: "no such client" }), {
						status: 404,
					}),
			),
		);
		const error = await apiGet("/clients/X").then(
			() => null,
			(e: ApiError) => e,
		);
		expect(error).toBeInstanceOf(ApiError);
		expect(error?.status).toBe(404);
		expect(error?.detail).toBe("no such client");
	});
	it("maps a network failure to status 0", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn(async () => Promise.reject(new TypeError("fail"))),
		);
		const error = await apiGet("/rm").then(
			() => null,
			(e: ApiError) => e,
		);
		expect(error?.status).toBe(0);
	});
});
