import { ForgeFlowAPIError, api } from "@/lib/api";
/**
 * Tests for ForgeFlow API Client (src/lib/api.ts).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const BASE_URL = "http://localhost:8000";

describe("ForgeFlowAPI", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	// ── GET ──

	it("get() returns parsed JSON on 200", async () => {
		const mockData = { code: 0, data: { tickets: [], total: 0 } };
		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
			new Response(JSON.stringify(mockData), { status: 200 }),
		);

		const result = await api.get("/api/v1/tickets");
		expect(result).toEqual(mockData);
		expect(globalThis.fetch).toHaveBeenCalledWith(
			`${BASE_URL}/api/v1/tickets`,
			expect.objectContaining({
				headers: expect.objectContaining({
					"Content-Type": "application/json",
					"X-Request-ID": expect.any(String),
				}),
			}),
		);
	});

	// ── POST ──

	it("post() sends JSON body and returns response", async () => {
		const body = { issue_text: "test" };
		const mockData = { code: 0, data: { ticket_id: "123" } };
		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
			new Response(JSON.stringify(mockData), { status: 200 }),
		);

		const result = await api.post("/api/v1/tickets", body);
		expect(result).toEqual(mockData);
		expect(globalThis.fetch).toHaveBeenCalledWith(
			`${BASE_URL}/api/v1/tickets`,
			expect.objectContaining({
				method: "POST",
				body: JSON.stringify(body),
			}),
		);
	});

	// ── PUT ──

	it("put() sends JSON body with PUT method", async () => {
		const body = { title: "updated" };
		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
			new Response(JSON.stringify({ code: 0, data: {} }), { status: 200 }),
		);

		await api.put("/api/v1/policies/1", body);
		expect(globalThis.fetch).toHaveBeenCalledWith(
			`${BASE_URL}/api/v1/policies/1`,
			expect.objectContaining({
				method: "PUT",
				body: JSON.stringify(body),
			}),
		);
	});

	// ── PATCH ──

	it("patch() sends JSON body with PATCH method", async () => {
		const body = { status: "resolved" };
		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
			new Response(JSON.stringify({ code: 0, data: {} }), { status: 200 }),
		);

		await api.patch("/api/v1/tickets/1", body);
		expect(globalThis.fetch).toHaveBeenCalledWith(
			`${BASE_URL}/api/v1/tickets/1`,
			expect.objectContaining({
				method: "PATCH",
				body: JSON.stringify(body),
			}),
		);
	});

	// ── DELETE ──

	it("delete() sends DELETE request", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
			new Response(JSON.stringify({ code: 0, data: {} }), { status: 200 }),
		);

		await api.delete("/api/v1/policies/1");
		expect(globalThis.fetch).toHaveBeenCalledWith(
			`${BASE_URL}/api/v1/policies/1`,
			expect.objectContaining({ method: "DELETE" }),
		);
	});

	// ── Error handling ──

	it("throws ForgeFlowAPIError with parsed JSON on non-2xx", async () => {
		const errorBody = { code: "NOT_FOUND", message: "Ticket not found" };
		vi.spyOn(globalThis, "fetch").mockImplementation(() =>
			Promise.resolve(new Response(JSON.stringify(errorBody), { status: 404 })),
		);

		await expect(api.get("/api/v1/tickets/missing")).rejects.toThrow(
			ForgeFlowAPIError,
		);
		await expect(api.get("/api/v1/tickets/missing")).rejects.toMatchObject({
			code: "NOT_FOUND",
			status: 404,
			message: "Ticket not found",
		});
	});

	it("throws ForgeFlowAPIError with NETWORK_ERROR on invalid JSON response", async () => {
		vi.spyOn(globalThis, "fetch").mockImplementation(() =>
			Promise.resolve(
				new Response("plain text error", {
					status: 500,
					statusText: "Internal Server Error",
				}),
			),
		);

		await expect(api.get("/api/v1/broken")).rejects.toThrow(ForgeFlowAPIError);
		await expect(api.get("/api/v1/broken")).rejects.toMatchObject({
			code: "NETWORK_ERROR",
			status: 500,
		});
	});

	// ── 204 No Content ──

	it("returns undefined for 204 No Content", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
			new Response(null, { status: 204 }),
		);

		const result = await api.delete("/api/v1/policies/1");
		expect(result).toBeUndefined();
	});

	// ── X-Request-ID header ──

	it("includes X-Request-ID header on every request", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
			new Response(JSON.stringify({}), { status: 200 }),
		);

		await api.get("/api/v1/health");
		const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
			.calls[0];
		const headers = callArgs[1].headers as Record<string, string>;
		expect(headers["X-Request-ID"]).toBeDefined();
		expect(headers["X-Request-ID"]).toMatch(
			/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
		);
	});
});
