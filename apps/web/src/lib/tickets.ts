/**
 * ForgeFlow — Ticket API Functions.
 *
 * Typed wrappers around the API client for all ticket operations.
 * Used by TanStack Query hooks throughout the dashboard.
 */

import type {
	ApprovalInput,
	ApprovalResult,
	DashboardStats,
	PaginatedData,
	TicketCreateInput,
	TicketCreateResult,
	TicketDetail,
	TicketListItem,
	TicketMetrics,
	TicketStatusInfo,
} from "@/types";
import { api } from "./api";

// ── Create ──

export async function createTicket(
	input: TicketCreateInput,
): Promise<TicketCreateResult> {
	const res = await api.post<{ code: number; data: TicketCreateResult }>(
		"/api/v1/tickets",
		input,
	);
	return res.data;
}

// ── List ──

export interface ListTicketsParams {
	page?: number;
	page_size?: number;
	status?: string;
	platform?: string;
}

export async function listTickets(
	params: ListTicketsParams = {},
): Promise<PaginatedData<TicketListItem>> {
	const searchParams = new URLSearchParams();
	if (params.page) searchParams.set("page", String(params.page));
	if (params.page_size) searchParams.set("page_size", String(params.page_size));
	if (params.status) searchParams.set("status", params.status);
	if (params.platform) searchParams.set("platform", params.platform);

	const qs = searchParams.toString();
	const res = await api.get<{
		code: number;
		data: PaginatedData<TicketListItem>;
	}>(`/api/v1/tickets${qs ? `?${qs}` : ""}`);
	return res.data;
}

// ── Detail ──

export async function getTicketDetail(ticketId: string): Promise<TicketDetail> {
	const res = await api.get<{ code: number; data: { ticket: TicketDetail } }>(
		`/api/v1/tickets/${ticketId}`,
	);
	return res.data.ticket;
}

// ── Status (REST poll fallback) ──

export async function getTicketStatus(
	ticketId: string,
): Promise<TicketStatusInfo> {
	const res = await api.get<{ code: number; data: TicketStatusInfo }>(
		`/api/v1/tickets/${ticketId}/status`,
	);
	return res.data;
}

// ── Approve / Reject ──

export async function approveTicket(
	ticketId: string,
	input: ApprovalInput = { approved: true },
): Promise<ApprovalResult> {
	const res = await api.post<{ code: number; data: ApprovalResult }>(
		`/api/v1/tickets/${ticketId}/approve`,
		input,
	);
	return res.data;
}

export async function rejectTicket(
	ticketId: string,
	note = "",
): Promise<ApprovalResult> {
	return approveTicket(ticketId, { approved: false, note });
}

// ── Cancel ──

export async function cancelTicket(
	ticketId: string,
): Promise<{ ticket_id: string; status: string }> {
	const res = await api.post<{
		code: number;
		data: { ticket_id: string; status: string };
	}>(`/api/v1/tickets/${ticketId}/cancel`);
	return res.data;
}

// ── Dashboard Stats ──

export async function getDashboardStats(): Promise<DashboardStats> {
	const res = await api.get<{ code: number; data: DashboardStats }>(
		"/api/v1/tickets/stats/dashboard",
	);
	return res.data;
}

export async function getTicketMetrics(days = 30): Promise<TicketMetrics> {
	const res = await api.get<{ code: number; data: TicketMetrics }>(
		`/api/v1/tickets/stats/metrics?days=${days}`,
	);
	return res.data;
}
