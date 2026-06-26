"use client";

import { ApprovalPanel } from "@/components/tickets/approval-panel";
import { StepTimeline } from "@/components/tickets/step-timeline";
import { useApprovalStore } from "@/lib/store";
import {
	approveTicket,
	cancelTicket,
	getTicketDetail,
	getTicketStatus,
	rejectTicket,
} from "@/lib/tickets";
import { useWebSocket } from "@/lib/use-websocket";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Wifi, WifiOff } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

const STATUS_COLORS: Record<string, string> = {
	received: "bg-slate-100 text-slate-700",
	processing: "bg-blue-100 text-blue-700",
	pending_approval: "bg-amber-100 text-amber-700",
	resolved: "bg-green-100 text-green-700",
	escalated: "bg-orange-100 text-orange-700",
	failed: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<string, string> = {
	received: "Received",
	processing: "Processing",
	pending_approval: "Pending Approval",
	resolved: "Resolved",
	escalated: "Escalated",
	failed: "Failed",
};

export default function TicketDetailPage() {
	const params = useParams<{ id: string }>();
	const _router = useRouter();
	const queryClient = useQueryClient();
	const ticketId = params.id;
	const { setSubmitting } = useApprovalStore();

	const [isApproving, setIsApproving] = useState(false);

	// ── REST initial load ──
	const {
		data: ticket,
		isLoading,
		isError,
	} = useQuery({
		queryKey: ["ticket", ticketId],
		queryFn: () => getTicketDetail(ticketId),
	});

	const { data: statusInfo } = useQuery({
		queryKey: ["ticket-status", ticketId],
		queryFn: () => getTicketStatus(ticketId),
	});

	// ── WebSocket for live updates ──
	const { lastEvent, isConnected } = useWebSocket({
		ticketId,
		onEvent: (event) => {
			// Invalidate queries so the UI refreshes with latest data
			if (
				event.type === "completed" ||
				event.type === "pending_approval" ||
				event.type === "execution_result"
			) {
				queryClient.invalidateQueries({ queryKey: ["ticket", ticketId] });
				queryClient.invalidateQueries({
					queryKey: ["ticket-status", ticketId],
				});
			}
		},
	});

	// ── Handlers ──
	const handleApprove = async (note: string) => {
		setIsApproving(true);
		setSubmitting(true);
		try {
			await approveTicket(ticketId, { approved: true, note });
			queryClient.invalidateQueries({ queryKey: ["ticket", ticketId] });
			queryClient.invalidateQueries({
				queryKey: ["ticket-status", ticketId],
			});
		} finally {
			setIsApproving(false);
			setSubmitting(false);
		}
	};

	const handleReject = async (note: string) => {
		setIsApproving(true);
		setSubmitting(true);
		try {
			await rejectTicket(ticketId, note);
			queryClient.invalidateQueries({ queryKey: ["ticket", ticketId] });
			queryClient.invalidateQueries({
				queryKey: ["ticket-status", ticketId],
			});
		} finally {
			setIsApproving(false);
			setSubmitting(false);
		}
	};

	const handleCancel = async () => {
		try {
			await cancelTicket(ticketId);
			queryClient.invalidateQueries({ queryKey: ["ticket", ticketId] });
		} catch {
			// ignore
		}
	};

	// ── Loading ──
	if (isLoading) {
		return (
			<div>
				<Link
					href="/dashboard/tickets"
					className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-4"
				>
					<ArrowLeft size={14} />
					Back to tickets
				</Link>
				<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
					<p className="text-slate-400">Loading ticket details...</p>
				</div>
			</div>
		);
	}

	// ── Error ──
	if (isError || !ticket) {
		return (
			<div>
				<Link
					href="/dashboard/tickets"
					className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 mb-4"
				>
					<ArrowLeft size={14} />
					Back to tickets
				</Link>
				<div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
					<p className="text-red-500">Failed to load ticket.</p>
					<p className="text-xs text-slate-400 mt-1">
						The ticket may not exist or the API is unavailable.
					</p>
				</div>
			</div>
		);
	}

	const status = ticket.status;
	const needsApproval =
		status === "pending_approval" || ticket.requires_approval;
	const isTerminal = ["resolved", "escalated", "failed"].includes(status);

	return (
		<div>
			{/* Header */}
			<div className="flex items-center justify-between mb-4">
				<div className="flex items-center gap-3">
					<Link
						href="/dashboard/tickets"
						className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
					>
						<ArrowLeft size={14} />
					</Link>
					<h1 className="text-xl font-bold text-slate-900 font-mono">
						{ticketId}
					</h1>
					<span
						className={`text-xs px-2 py-0.5 rounded-full font-medium ${
							STATUS_COLORS[status] ?? "bg-slate-100 text-slate-700"
						}`}
					>
						{STATUS_LABELS[status] ?? status}
					</span>
					{/* WebSocket indicator */}
					<span
						className={`inline-flex items-center gap-1 text-xs ${
							isConnected ? "text-green-600" : "text-slate-400"
						}`}
					>
						{isConnected ? <Wifi size={12} /> : <WifiOff size={12} />}
						{isConnected ? "Live" : "Polling"}
					</span>
				</div>

				{/* Cancel button (only for active tickets) */}
				{!isTerminal && status !== "pending_approval" && (
					<button
						type="button"
						onClick={handleCancel}
						className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
					>
						Cancel Ticket
					</button>
				)}
			</div>

			<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
				{/* Left: Details + Timeline */}
				<div className="lg:col-span-2 space-y-6">
					{/* Customer & Issue Info */}
					<div className="bg-white rounded-xl border border-slate-200 p-5">
						<h3 className="text-sm font-semibold text-slate-700 mb-3">
							Ticket Information
						</h3>
						<dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
							<div>
								<dt className="text-slate-400">Customer</dt>
								<dd className="text-slate-900 font-medium">
									{ticket.customer_name || ticket.customer_email}
								</dd>
							</div>
							<div>
								<dt className="text-slate-400">Email</dt>
								<dd className="text-slate-900">{ticket.customer_email}</dd>
							</div>
							<div>
								<dt className="text-slate-400">Platform</dt>
								<dd className="text-slate-900 capitalize">{ticket.platform}</dd>
							</div>
							<div>
								<dt className="text-slate-400">Order ID</dt>
								<dd className="text-slate-900 font-mono text-xs">
									{ticket.order_id || "—"}
								</dd>
							</div>
							<div className="sm:col-span-2">
								<dt className="text-slate-400">Issue</dt>
								<dd className="text-slate-900 mt-1 leading-relaxed">
									{ticket.issue_text}
								</dd>
							</div>
						</dl>
					</div>

					{/* Agent Analysis */}
					<div className="bg-white rounded-xl border border-slate-200 p-5">
						<h3 className="text-sm font-semibold text-slate-700 mb-3">
							Agent Analysis
						</h3>
						<div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
							<div>
								<dt className="text-slate-400 text-xs">Intent</dt>
								<dd className="text-slate-900 font-medium mt-0.5 capitalize">
									{ticket.intent?.replace(/_/g, " ") ?? "—"}
								</dd>
							</div>
							<div>
								<dt className="text-slate-400 text-xs">Confidence</dt>
								<dd className="text-slate-900 font-medium mt-0.5">
									{ticket.confidence != null
										? `${(ticket.confidence * 100).toFixed(0)}%`
										: "—"}
								</dd>
							</div>
							<div>
								<dt className="text-slate-400 text-xs">Urgency</dt>
								<dd className="text-slate-900 font-medium mt-0.5 capitalize">
									{ticket.urgency ?? "—"}
								</dd>
							</div>
							<div>
								<dt className="text-slate-400 text-xs">Sentiment</dt>
								<dd className="text-slate-900 font-medium mt-0.5 capitalize">
									{ticket.sentiment ?? "—"}
								</dd>
							</div>
							<div>
								<dt className="text-slate-400 text-xs">Language</dt>
								<dd className="text-slate-900 font-medium mt-0.5 uppercase">
									{ticket.issue_language ?? "—"}
								</dd>
							</div>
						</div>

						{/* Decision details */}
						{ticket.recommended_action && (
							<div className="mt-4 pt-4 border-t border-slate-100">
								<div className="grid grid-cols-2 gap-3 text-sm mb-3">
									<div>
										<span className="text-slate-400 text-xs">
											Recommended Action
										</span>
										<p className="text-slate-900 font-medium capitalize">
											{ticket.recommended_action.replace(/_/g, " ")}
										</p>
									</div>
									{ticket.refund_amount != null && ticket.refund_amount > 0 && (
										<div>
											<span className="text-slate-400 text-xs">
												Refund Amount
											</span>
											<p className="text-slate-900 font-medium">
												${ticket.refund_amount.toFixed(2)}
											</p>
										</div>
									)}
								</div>
								{ticket.decision_explanation && (
									<div className="bg-slate-50 rounded-lg p-3">
										<span className="text-xs text-slate-400">Reasoning</span>
										<p className="text-sm text-slate-700 mt-1 leading-relaxed">
											{ticket.decision_explanation}
										</p>
									</div>
								)}
							</div>
						)}
					</div>

					{/* Step Timeline */}
					<StepTimeline
						steps={statusInfo?.steps ?? []}
						progress={statusInfo?.progress ?? 0}
					/>

					{/* Execution Result (after completion) */}
					{ticket.execution_result && (
						<div className="bg-white rounded-xl border border-slate-200 p-5">
							<h3 className="text-sm font-semibold text-slate-700 mb-3">
								Execution Result
							</h3>
							<pre className="text-xs text-slate-600 bg-slate-50 rounded-lg p-3 overflow-auto max-h-48">
								{JSON.stringify(ticket.execution_result, null, 2)}
							</pre>
						</div>
					)}

					{/* Error (if any) */}
					{ticket.error_message && (
						<div className="bg-red-50 border border-red-200 rounded-xl p-5">
							<h3 className="text-sm font-semibold text-red-700 mb-1">Error</h3>
							<p className="text-sm text-red-600">{ticket.error_message}</p>
						</div>
					)}
				</div>

				{/* Right: Approval Panel */}
				<div className="space-y-4">
					{needsApproval && statusInfo?.pending_approval && (
						<ApprovalPanel
							approval={statusInfo.pending_approval}
							onApprove={handleApprove}
							onReject={handleReject}
							isSubmitting={isApproving}
						/>
					)}

					{/* Live Event Log */}
					{lastEvent && (
						<div className="bg-white rounded-xl border border-slate-200 p-5">
							<h3 className="text-sm font-semibold text-slate-700 mb-2">
								Latest Event
							</h3>
							<div className="text-xs font-mono bg-slate-50 rounded-lg p-3 overflow-auto max-h-48">
								<pre>{JSON.stringify(lastEvent, null, 2)}</pre>
							</div>
						</div>
					)}

					{/* Meta info */}
					<div className="bg-white rounded-xl border border-slate-200 p-5">
						<h3 className="text-sm font-semibold text-slate-700 mb-2">
							Processing Info
						</h3>
						<dl className="text-xs space-y-2">
							<div className="flex justify-between">
								<dt className="text-slate-400">Duration</dt>
								<dd className="text-slate-700">
									{ticket.processing_duration_ms != null
										? `${(ticket.processing_duration_ms / 1000).toFixed(1)}s`
										: "—"}
								</dd>
							</div>
							<div className="flex justify-between">
								<dt className="text-slate-400">Retries</dt>
								<dd className="text-slate-700">{ticket.retry_count}</dd>
							</div>
							<div className="flex justify-between">
								<dt className="text-slate-400">Created</dt>
								<dd className="text-slate-700">
									{ticket.created_at
										? new Date(ticket.created_at).toLocaleString()
										: "—"}
								</dd>
							</div>
							{ticket.completed_at && (
								<div className="flex justify-between">
									<dt className="text-slate-400">Completed</dt>
									<dd className="text-slate-700">
										{new Date(ticket.completed_at).toLocaleString()}
									</dd>
								</div>
							)}
						</dl>
					</div>
				</div>
			</div>
		</div>
	);
}
