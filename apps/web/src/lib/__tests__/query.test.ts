import { defaultQueryClient } from "@/lib/query";
/**
 * Tests for TanStack Query client config (src/lib/query.ts).
 */
import { describe, expect, it } from "vitest";

describe("defaultQueryClient", () => {
	it("has expected staleTime", () => {
		expect(defaultQueryClient.getDefaultOptions().queries?.staleTime).toBe(
			30_000,
		);
	});

	it("has expected gcTime", () => {
		expect(defaultQueryClient.getDefaultOptions().queries?.gcTime).toBe(
			5 * 60 * 1000,
		);
	});

	it("has expected query retry count", () => {
		expect(defaultQueryClient.getDefaultOptions().queries?.retry).toBe(2);
	});

	it("has refetchOnWindowFocus disabled", () => {
		expect(
			defaultQueryClient.getDefaultOptions().queries?.refetchOnWindowFocus,
		).toBe(false);
	});

	it("has expected mutation retry count", () => {
		expect(defaultQueryClient.getDefaultOptions().mutations?.retry).toBe(1);
	});
});
