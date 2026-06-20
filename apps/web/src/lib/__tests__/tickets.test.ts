import * as apiModule from "@/lib/api";
import type { TicketCreateInput } from "@/types";
/**
 * Tests for Ticket API functions (src/lib/tickets.ts).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

// Import functions under test
import {
	approveTicket,
	cancelTicket,
	createTicket,
	getDashboardStats,
	getTicketDetail,
	getTicketStatus,
	listTickets,
	rejectTicket,
} from "@/lib/tickets";

vi.mock("@/lib/api", () => ({
	api: {
		get: vi.fn(),
		post: vi.fn(),
		put: vi.fn(),
		patch: vi.fn(),
		delete: vi.fn(),
	},
}));

const api = apiModule.api as ReturnType<typeof vi.fn> & {
	get: ReturnType<typeof vi.fn>;
	post: ReturnType<typeof vi.fn>;
	put: ReturnType<typeof vi.fn>;
};

describe("tickets API", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	// ── createTicket ──

	it("createTicket calls POST /api/v1/tickets with input", async () => {
		const input: TicketCreateInput = {
			customer_email: "a@b.com",
			issue_text: "delayed",
		};
		(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { ticket_id: "1", status: "received" },
		});

		const result = await createTicket(input);
		expect(api.post).toHaveBeenCalledWith("/api/v1/tickets", input);
		expect(result).toEqual({ ticket_id: "1", status: "received" });
	});

	// ── listTickets ──

	it("listTickets calls GET /api/v1/tickets with no params", async () => {
		const mockPaginated = { tickets: [], total: 0, page: 1, page_size: 20 };
		(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: mockPaginated,
		});

		const result = await listTickets();
		expect(api.get).toHaveBeenCalledWith("/api/v1/tickets");
		expect(result).toEqual(mockPaginated);
	});

	it("listTickets builds query string from params", async () => {
		(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { tickets: [], total: 0 },
		});

		await listTickets({ page: 2, page_size: 10, status: "pending_approval" });
		expect(api.get).toHaveBeenCalledWith(
			"/api/v1/tickets?page=2&page_size=10&status=pending_approval",
		);
	});

	// ── getTicketDetail ──

	it("getTicketDetail calls GET /api/v1/tickets/:id", async () => {
		const mockTicket = { ticket_id: "abc", status: "processing" };
		(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { ticket: mockTicket },
		});

		const result = await getTicketDetail("abc");
		expect(api.get).toHaveBeenCalledWith("/api/v1/tickets/abc");
		expect(result).toEqual(mockTicket);
	});

	// ── getTicketStatus ──

	it("getTicketStatus calls GET /api/v1/tickets/:id/status", async () => {
		const mockStatus = {
			ticket_id: "1",
			status: "processing",
			progress: 50,
			steps: [],
			pending_approval: null,
		};
		(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: mockStatus,
		});

		await getTicketStatus("1");
		expect(api.get).toHaveBeenCalledWith("/api/v1/tickets/1/status");
	});

	// ── approveTicket ──

	it("approveTicket calls POST /api/v1/tickets/:id/approve with default input", async () => {
		const mockResult = {
			ticket_id: "1",
			status: "resolved",
			execution_id: "exec-1",
		};
		(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: mockResult,
		});

		const result = await approveTicket("1");
		expect(api.post).toHaveBeenCalledWith("/api/v1/tickets/1/approve", {
			approved: true,
		});
		expect(result).toEqual(mockResult);
	});

	it("approveTicket sends custom approval input", async () => {
		(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: {},
		});

		await approveTicket("1", { approved: false, note: "needs review" });
		expect(api.post).toHaveBeenCalledWith("/api/v1/tickets/1/approve", {
			approved: false,
			note: "needs review",
		});
	});

	// ── rejectTicket ──

	it("rejectTicket calls approveTicket with approved=false", async () => {
		const mockResult = {
			ticket_id: "1",
			status: "escalated",
			execution_id: null,
		};
		(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: mockResult,
		});

		const result = await rejectTicket("1", "invalid request");
		expect(api.post).toHaveBeenCalledWith("/api/v1/tickets/1/approve", {
			approved: false,
			note: "invalid request",
		});
		expect(result.status).toBe("escalated");
	});

	// ── cancelTicket ──

	it("cancelTicket calls POST /api/v1/tickets/:id/cancel", async () => {
		(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: { ticket_id: "1", status: "failed" },
		});

		const result = await cancelTicket("1");
		expect(api.post).toHaveBeenCalledWith("/api/v1/tickets/1/cancel");
		expect(result).toEqual({ ticket_id: "1", status: "failed" });
	});

	// ── getDashboardStats ──

	it("getDashboardStats calls GET /api/v1/tickets/stats/dashboard", async () => {
		const mockStats = {
			total_tickets: 10,
			resolved: 5,
			escalated: 2,
			pending_approval: 1,
			failed: 2,
			avg_processing_time_ms: 3000,
			auto_resolution_rate: 0.6,
		};
		(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
			code: 0,
			data: mockStats,
		});

		const result = await getDashboardStats();
		expect(api.get).toHaveBeenCalledWith("/api/v1/tickets/stats/dashboard");
		expect(result).toEqual(mockStats);
	});
});
