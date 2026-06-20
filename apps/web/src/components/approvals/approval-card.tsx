"use client";

import { AlertTriangle, Check, DollarSign, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { TicketListItem } from "@/types";

interface ApprovalCardProps {
	ticket: TicketListItem;
	onApprove: (ticketId: string, note: string) => Promise<void>;
	onReject: (ticketId: string, note: string) => Promise<void>;
	isSubmitting: boolean;
}

export function ApprovalCard({
	ticket,
	onApprove,
	onReject,
	isSubmitting,
}: ApprovalCardProps) {
	const [note, setNote] = useState("");
	const [mode, setMode] = useState<
		"idle" | "confirm_approve" | "confirm_reject"
	>("idle");

	const handleConfirm = async () => {
		if (mode === "confirm_approve") {
			await onApprove(ticket.ticket_id, note);
		} else if (mode === "confirm_reject") {
			await onReject(ticket.ticket_id, note);
		}
		setMode("idle");
	};

	const reset = () => {
		setMode("idle");
		setNote("");
	};

	return (
		<div className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-sm transition-shadow">
			<div className="flex items-start justify-between mb-3">
				<div>
					<Link
						href={`/dashboard/tickets/${ticket.ticket_id}`}
						className="text-sm font-mono text-brand-600 hover:text-brand-700 hover:underline"
					>
						{ticket.ticket_id}
					</Link>
					<p className="text-sm font-medium text-slate-900 mt-1">
						{ticket.customer_name || ticket.customer_email}
					</p>
					<p className="text-xs text-slate-400">{ticket.customer_email}</p>
				</div>
				<span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-50 px-2 py-1 rounded-full">
					<AlertTriangle size={12} />
					Needs Review
				</span>
			</div>

			{/* Issue summary */}
			<p className="text-sm text-slate-600 mb-3 line-clamp-2">
				{ticket.issue_text}
			</p>

			{/* Action & Amount */}
			<div className="flex items-center gap-4 mb-4 text-sm">
				<div>
					<span className="text-slate-400 text-xs">Action:</span>{" "}
					<span className="font-medium text-slate-800 capitalize">
						{ticket.recommended_action?.replace(/_/g, " ") ?? "—"}
					</span>
				</div>
				{ticket.refund_amount != null && ticket.refund_amount > 0 && (
					<div className="flex items-center gap-1">
						<DollarSign size={14} className="text-slate-400" />
						<span className="font-medium text-slate-800">
							{ticket.refund_amount.toFixed(2)}
						</span>
					</div>
				)}
			</div>

			{/* Note input */}
			<div className="mb-3">
				<input
					type="text"
					value={note}
					onChange={(e) => setNote(e.target.value)}
					placeholder="Add a note (optional)..."
					className="w-full px-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
					disabled={isSubmitting}
				/>
			</div>

			{/* Action buttons */}
			{mode === "idle" ? (
				<div className="flex gap-2">
					<button
						type="button"
						onClick={() => setMode("confirm_approve")}
						disabled={isSubmitting}
						className="flex-1 inline-flex items-center justify-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
					>
						<Check size={12} />
						Approve
					</button>
					<button
						type="button"
						onClick={() => setMode("confirm_reject")}
						disabled={isSubmitting}
						className="flex-1 inline-flex items-center justify-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50 transition-colors"
					>
						<X size={12} />
						Reject
					</button>
				</div>
			) : (
				<div className="space-y-2">
					<p className="text-xs font-medium text-slate-700">
						Confirm {mode === "confirm_approve" ? "approval" : "rejection"}?
					</p>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={handleConfirm}
							disabled={isSubmitting}
							className={`flex-1 px-3 py-1.5 text-xs font-medium text-white rounded-lg disabled:opacity-50 transition-colors ${
								mode === "confirm_approve"
									? "bg-green-600 hover:bg-green-700"
									: "bg-red-600 hover:bg-red-700"
							}`}
						>
							{isSubmitting ? "..." : "Yes"}
						</button>
						<button
							type="button"
							onClick={reset}
							disabled={isSubmitting}
							className="flex-1 px-3 py-1.5 text-xs font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 transition-colors"
						>
							Cancel
						</button>
					</div>
				</div>
			)}

			{/* Date */}
			<p className="text-xs text-slate-400 mt-3">
				Created:{" "}
				{ticket.created_at ? new Date(ticket.created_at).toLocaleString() : "—"}
			</p>
		</div>
	);
}
