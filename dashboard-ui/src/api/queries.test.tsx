import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useData } from "./queries";

afterEach(() => vi.restoreAllMocks());

const wrapper = ({ children }: { children: ReactNode }) => (
	<QueryClientProvider
		client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
	>
		{children}
	</QueryClientProvider>
);

describe("useData", () => {
	it("reports an error, not endless loading, when /as-of fails", async () => {
		vi.stubGlobal(
			"fetch",
			vi.fn(async () => Promise.reject(new TypeError("down"))),
		);
		const { result } = renderHook(() => useData("/clients"), { wrapper });
		await waitFor(() => expect(result.current.isError).toBe(true));
		expect(result.current.isPending).toBe(false);
	});
	it("fetches with the latest as_of", async () => {
		const fetchMock = vi.fn(
			async (url: string) =>
				new Response(
					JSON.stringify(
						url.includes("/as-of")
							? { as_of_dates: ["2026-08-26"], latest: "2026-08-26" }
							: { ok: 1 },
					),
				),
		);
		vi.stubGlobal("fetch", fetchMock);
		const { result } = renderHook(() => useData("/clients"), { wrapper });
		await waitFor(() => expect(result.current.data).toEqual({ ok: 1 }));
		expect(fetchMock.mock.calls.map((c) => c[0])).toContain(
			"/api/clients?as_of=2026-08-26",
		);
	});
});
