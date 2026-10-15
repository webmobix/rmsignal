import {
	queryOptions,
	type UseQueryResult,
	useQuery,
} from "@tanstack/react-query";
import { apiGet, type Params, type Schemas } from "./client";

export type AsOfResponse = Schemas["AsOfResponse"];
export type RmProfile = Schemas["RmProfile"];
export type Overview = Schemas["ApiOverview"];
export type ApiAction = Schemas["ApiAction"];
export type ClientDetail = Schemas["ClientDetail"];

/** Query key always starts with the as_of so each point in time caches apart. */
export function dataQuery<T>(
	asOf: string | null | undefined,
	path: string,
	params: Params = {},
) {
	return queryOptions({
		queryKey: ["data", asOf, path, params],
		queryFn: ({ signal }) => apiGet<T>(path, params, asOf, signal),
		enabled: Boolean(asOf),
	});
}

export const asOfQuery = queryOptions({
	queryKey: ["as-of"],
	queryFn: ({ signal }) =>
		apiGet<AsOfResponse>("/as-of", {}, undefined, signal),
	staleTime: 60_000,
});

export function useAsOf(): string | undefined {
	return useQuery(asOfQuery).data?.latest ?? undefined;
}

/**
 * Data for the latest as_of. The query stays disabled until the date is known, so a
 * failed `/as-of` request is reported as this query's error (with retry), not as a
 * spinner that never ends.
 */
export function useData<T>(
	path: string,
	params: Params = {},
): UseQueryResult<T> {
	const asOfQuery_ = useQuery(asOfQuery);
	const query = useQuery(dataQuery<T>(asOfQuery_.data?.latest, path, params));
	if (asOfQuery_.isError) {
		return {
			...query,
			isError: true,
			isPending: false,
			error: asOfQuery_.error,
			refetch: () => asOfQuery_.refetch(),
		} as unknown as UseQueryResult<T>;
	}
	return query;
}

export function useRm(): UseQueryResult<RmProfile> {
	return useData<RmProfile>("/rm");
}
