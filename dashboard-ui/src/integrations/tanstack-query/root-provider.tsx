import { QueryClient } from "@tanstack/react-query";

export function getContext() {
	const queryClient = new QueryClient({
		defaultOptions: { queries: { retry: false, staleTime: 30_000 } },
	});

	return {
		queryClient,
	};
}
export default function TanstackQueryProvider() {}
