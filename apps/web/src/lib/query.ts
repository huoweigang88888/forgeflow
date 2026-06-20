/**
 * TanStack Query — Default client configuration.
 *
 * Phase 0: Basic setup with sensible defaults.
 * Phase 2: Add query keys factory, optimistic updates, prefetching.
 */

import { QueryClient } from "@tanstack/react-query";

export const defaultQueryClient = new QueryClient({
	defaultOptions: {
		queries: {
			staleTime: 30 * 1000, // Data is fresh for 30 seconds
			gcTime: 5 * 60 * 1000, // Cache for 5 minutes
			retry: 2,
			refetchOnWindowFocus: false,
		},
		mutations: {
			retry: 1,
		},
	},
});
