import * as apiModule from "@/lib/api";
/**
 * Tests for Policy API functions (src/lib/policies.ts).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
	createPolicy,
	deletePolicy,
	getPolicy,
	listPolicies,
	searchPolicies,
	updatePolicy,
} from "@/lib/policies";

vi.mock("@/lib/api", () => ({
	api: {
		get: vi.fn(),
		post: vi.fn(),
		put: vi.fn(),
		delete: vi.fn(),
	},
}));

const api = apiModule.api as ReturnType<typeof vi.fn> & {
	get: ReturnType<typeof vi.fn>;
	post: ReturnType<typeof vi.fn>;
	put: ReturnType<typeof vi.fn>;
	delete: ReturnType<typeof vi.fn>;
};

const mockPolicy = {
	id: "p1",
	title: "Refund Policy",
	content: "...",
	content_hash: "abc",
	chunk_index: 0,
	source_document_id: null,
	category: "refund",
	tags: [],
	is_active: true,
	version: 1,
	uploaded_by: null,
	uploaded_at: null,
	created_at: null,
	updated_at: null,
};

describe("policies API", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("createPolicy calls POST /api/v1/policies", async () => {
		const input = { title: "New Policy", content: "test" };
		(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { policy: mockPolicy },
		});

		const result = await createPolicy(input);
		expect(api.post).toHaveBeenCalledWith("/api/v1/policies", input);
		expect(result).toEqual(mockPolicy);
	});

	it("listPolicies calls GET /api/v1/policies with default (no args)", async () => {
		(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { policies: [], total: 0 },
		});

		await listPolicies();
		expect(api.get).toHaveBeenCalledWith("/api/v1/policies");
	});

	it("listPolicies builds query string from all params", async () => {
		(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { policies: [], total: 0 },
		});

		await listPolicies({ page: 2, page_size: 5, category: "refund" });
		expect(api.get).toHaveBeenCalledWith(
			"/api/v1/policies?page=2&page_size=5&category=refund",
		);
	});

	it("getPolicy calls GET /api/v1/policies/:id", async () => {
		(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { policy: mockPolicy },
		});

		const result = await getPolicy("p1");
		expect(api.get).toHaveBeenCalledWith("/api/v1/policies/p1");
		expect(result).toEqual(mockPolicy);
	});

	it("updatePolicy calls PUT /api/v1/policies/:id", async () => {
		const input = { title: "Updated Title" };
		(api.put as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { policy: { ...mockPolicy, ...input } },
		});

		const result = await updatePolicy("p1", input);
		expect(api.put).toHaveBeenCalledWith("/api/v1/policies/p1", input);
		expect(result.title).toBe("Updated Title");
	});

	it("deletePolicy calls DELETE /api/v1/policies/:id", async () => {
		(api.delete as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { id: "p1" },
		});

		await deletePolicy("p1");
		expect(api.delete).toHaveBeenCalledWith("/api/v1/policies/p1");
	});

	it("searchPolicies calls POST /api/v1/policies/search with defaults", async () => {
		(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { hits: [], query: "refund", total: 0 },
		});

		await searchPolicies("refund");
		expect(api.post).toHaveBeenCalledWith("/api/v1/policies/search", {
			query: "refund",
			category: undefined,
			limit: 5,
			threshold: 0.7,
		});
	});

	it("searchPolicies passes all options", async () => {
		(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { hits: [], query: "x", total: 0 },
		});

		await searchPolicies("shipping", {
			category: "logistics",
			limit: 10,
			threshold: 0.8,
		});
		expect(api.post).toHaveBeenCalledWith("/api/v1/policies/search", {
			query: "shipping",
			category: "logistics",
			limit: 10,
			threshold: 0.8,
		});
	});
});
