"use client";

import { ApprovalCard } from "@/components/approvals/approval-card";
import { useApprovalStore } from "@/lib/store";
import { approveTicket, listTickets, rejectTicket } from "@/lib/tickets";
import type { TicketListItem } from "@/types";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

export default function ApprovalsPage() {
	const queryClient = useQueryClient();
	const { setSubmitting } = useApprovalStore();
	const [processingId, setProcessingId] = useState<string | null>(null);
	const { t } = useTranslation();

	const { data, isLoading, isError } = useQuery({
		queryKey: ["tickets", { status: "pending_approval" }],
		queryFn: () =>
			listTickets({ page: 1, page_size: 50, status: "pending_approval" }),
		refetchInterval: 15_000,
	});

	const handleApprove = async (ticketId: string, note: string) => {
		setProcessingId(ticketId);
		setSubmitting(true);
		try {
			await approveTicket(ticketId, { approved: true, note });
			queryClient.invalidateQueries({
				queryKey: ["tickets", { status: "pending_approval" }],
			});
			queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
		} finally {
			setProcessingId(null);
			setSubmitting(false);
		}
	};

	const handleReject = async (ticketId: string, note: string) => {
		setProcessingId(ticketId);
		setSubmitting(true);
		try {
			await rejectTicket(ticketId, note);
			queryClient.invalidateQueries({
				queryKey: ["tickets", { status: "pending_approval" }],
			});
			queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
		} finally {
			setProcessingId(null);
			setSubmitting(false);
		}
	};

	const tickets: TicketListItem[] = data?.tickets ?? [];

	return (
		<div>
			<div className="flex items-center justify-between mb-2">
				<h1 className="text-2xl font-bold text-slate-900">
					{t("approvals.title")}
				</h1>
				{tickets.length > 0 && (
					<span className="text-sm text-slate-500">
						{t("approvals.pending", { n: tickets.length })}
					</span>
				)}
			</div>
			<p className="text-slate-500 mb-6">{t("approvals.subtitle")}</p>

			{/* Loading */}
			{isLoading && (
				<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
					<p className="text-slate-400">{t("approvals.loading")}</p>
				</div>
			)}

			{/* Error */}
			{isError && (
				<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
					<p className="text-red-500">{t("approvals.failedToLoad")}</p>
				</div>
			)}

			{/* Empty */}
			{!isLoading && !isError && tickets.length === 0 && (
				<div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
					<CheckCircle2 size={40} className="mx-auto text-green-300 mb-4" />
					<p className="text-slate-500 font-medium">
						{t("approvals.allClear")}
					</p>
					<p className="text-sm text-slate-400 mt-1">
						{t("approvals.noTickets")}
					</p>
				</div>
			)}

			{/* Approval Cards */}
			{!isLoading && !isError && tickets.length > 0 && (
				<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
					{tickets.map((ticket) => (
						<ApprovalCard
							key={ticket.ticket_id}
							ticket={ticket}
							onApprove={handleApprove}
							onReject={handleReject}
							isSubmitting={processingId === ticket.ticket_id}
						/>
					))}
				</div>
			)}
		</div>
	);
}
