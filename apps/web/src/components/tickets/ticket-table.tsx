"use client";

import type { TicketListItem, TicketStatus } from "@/types";
import Link from "next/link";

const STATUS_COLORS: Record<TicketStatus, string> = {
	received: "bg-slate-100 text-slate-700",
	processing: "bg-blue-100 text-blue-700",
	pending_approval: "bg-amber-100 text-amber-700",
	resolved: "bg-green-100 text-green-700",
	escalated: "bg-orange-100 text-orange-700",
	failed: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<TicketStatus, string> = {
	received: "Received",
	processing: "Processing",
	pending_approval: "Pending",
	resolved: "Resolved",
	escalated: "Escalated",
	failed: "Failed",
};

const INTENT_LABELS: Record<string, string> = {
	shipping_delay: "Shipping Delay",
	refund_request: "Refund Request",
	wrong_item: "Wrong Item",
	damaged_item: "Damaged Item",
	exchange_request: "Exchange",
	partial_refund: "Partial Refund",
	subscription_cancel: "Cancel Subscription",
	pre_sale_inquiry: "Pre-Sale Inquiry",
	other: "Other",
};

const PLATFORM_LABELS: Record<string, string> = {
	shopify: "Shopify",
	woocommerce: "WooCommerce",
	amazon: "Amazon",
	mock: "Mock",
};

interface TicketTableProps {
	tickets: TicketListItem[];
	isLoading: boolean;
}

export function TicketTable({ tickets, isLoading }: TicketTableProps) {
	if (isLoading) {
		return (
			<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
				<p className="text-slate-400">Loading tickets...</p>
			</div>
		);
	}

	if (tickets.length === 0) {
		return (
			<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
				<p className="text-slate-400">No tickets found.</p>
				<p className="text-xs text-slate-300 mt-1">
					Create a ticket via the API to see it here.
				</p>
			</div>
		);
	}

	return (
		<div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
			<div className="overflow-x-auto">
				<table className="w-full">
					<thead>
						<tr className="border-b border-slate-100 bg-slate-50/50">
							<th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
								Ticket ID
							</th>
							<th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
								Platform
							</th>
							<th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
								Customer
							</th>
							<th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
								Intent
							</th>
							<th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
								Status
							</th>
							<th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
								Action
							</th>
							<th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
								Date
							</th>
						</tr>
					</thead>
					<tbody className="divide-y divide-slate-50">
						{tickets.map((ticket) => (
							<tr
								key={ticket.ticket_id}
								className="hover:bg-slate-50 transition-colors"
							>
								<td className="px-5 py-3">
									<Link
										href={`/dashboard/tickets/${ticket.ticket_id}`}
										className="text-sm font-mono text-brand-600 hover:text-brand-700 hover:underline"
									>
										{ticket.ticket_id}
									</Link>
								</td>
								<td className="px-5 py-3">
									<span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-100 text-slate-600">
										{ticket.platform
											? (PLATFORM_LABELS[ticket.platform] ?? ticket.platform)
											: "—"}
									</span>
								</td>
								<td className="px-5 py-3">
									<div>
										<p className="text-sm font-medium text-slate-900">
											{ticket.customer_name || ticket.customer_email}
										</p>
										<p className="text-xs text-slate-400 truncate max-w-[200px]">
											{ticket.issue_text.slice(0, 60)}
											{ticket.issue_text.length > 60 ? "…" : ""}
										</p>
									</div>
								</td>
								<td className="px-5 py-3">
									<span className="text-sm text-slate-600">
										{ticket.intent
											? (INTENT_LABELS[ticket.intent] ?? ticket.intent)
											: "—"}
									</span>
								</td>
								<td className="px-5 py-3">
									<span
										className={`text-xs px-2 py-0.5 rounded-full font-medium ${
											STATUS_COLORS[ticket.status]
										}`}
									>
										{STATUS_LABELS[ticket.status]}
									</span>
								</td>
								<td className="px-5 py-3">
									<span className="text-sm text-slate-600">
										{ticket.recommended_action
											? ticket.recommended_action.replace(/_/g, " ")
											: "—"}
									</span>
									{ticket.refund_amount != null && ticket.refund_amount > 0 && (
										<span className="text-xs text-slate-400 ml-1">
											(${ticket.refund_amount.toFixed(2)})
										</span>
									)}
								</td>
								<td className="px-5 py-3">
									<span className="text-xs text-slate-400">
										{ticket.created_at
											? new Date(ticket.created_at).toLocaleDateString()
											: "—"}
									</span>
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	);
}
