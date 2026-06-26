"use client";

import type { PendingApproval } from "@/types";
import { AlertTriangle, Check, Clock, X } from "lucide-react";
import { useEffect, useState } from "react";

interface ApprovalPanelProps {
	approval: PendingApproval;
	onApprove: (note: string) => Promise<void>;
	onReject: (note: string) => Promise<void>;
	isSubmitting: boolean;
}

function formatSlaCountdown(remainingSeconds: number): string {
	if (remainingSeconds <= 0) return "00:00:00";
	const h = Math.floor(remainingSeconds / 3600);
	const m = Math.floor((remainingSeconds % 3600) / 60);
	const s = remainingSeconds % 60;
	if (remainingSeconds > 7200) {
		return `${h}h ${m}m remaining`;
	}
	return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function ApprovalPanel({
	approval,
	onApprove,
	onReject,
	isSubmitting,
}: ApprovalPanelProps) {
	const [note, setNote] = useState("");
	const [showConfirm, setShowConfirm] = useState<"approve" | "reject" | null>(
		null,
	);

	// Client-side countdown from sla_remaining_seconds
	const [countdown, setCountdown] = useState<number | null>(
		approval.sla_remaining_seconds ?? null,
	);
	const [breached, setBreached] = useState(approval.sla_breached ?? false);

	useEffect(() => {
		const initial = approval.sla_remaining_seconds;
		if (initial == null) {
			setCountdown(null);
			setBreached(false);
			return;
		}
		let remaining = initial;
		setCountdown(remaining);
		setBreached(remaining <= 0);

		const interval = setInterval(() => {
			remaining = Math.max(0, remaining - 1);
			setCountdown(remaining);
			setBreached(remaining <= 0);
			if (remaining <= 0) clearInterval(interval);
		}, 1000);

		return () => clearInterval(interval);
	}, [approval.sla_remaining_seconds, approval.sla_breached]);

	const handleConfirm = async () => {
		if (!showConfirm) return;
		if (showConfirm === "approve") {
			await onApprove(note);
		} else {
			await onReject(note);
		}
		setShowConfirm(null);
	};

	return (
		<div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
			<div className="flex items-start gap-3 mb-4">
				<div className="p-2 bg-amber-100 rounded-lg shrink-0">
					<AlertTriangle size={18} className="text-amber-600" />
				</div>
				<div>
					<h3 className="text-sm font-semibold text-amber-800">
						Approval Required
					</h3>
					<p className="text-sm text-amber-700 mt-1">
						This ticket requires human review before proceeding.
					</p>
				</div>
			</div>

			{/* SLA Countdown */}
			{countdown != null && (
				<div
					className={`flex items-center gap-2 mb-4 px-3 py-2 rounded-lg text-sm font-medium ${
						breached
							? "bg-red-100 text-red-700"
							: countdown < 7200
								? "bg-amber-100 text-amber-700"
								: "bg-white text-slate-600 border border-slate-200"
					}`}
				>
					<Clock size={16} />
					{breached ? (
						<span>SLA Deadline Breached — escalate immediately</span>
					) : (
						<span>
							Time remaining: {formatSlaCountdown(countdown)}
						</span>
					)}
				</div>
			)}

			{/* Details */}
			<div className="grid grid-cols-2 gap-3 mb-4 text-sm">
				<div>
					<span className="text-slate-500">Action:</span>{" "}
					<span className="font-medium text-slate-800 capitalize">
						{approval.action?.replace(/_/g, " ") ?? "unknown"}
					</span>
				</div>
				{approval.amount != null && approval.amount > 0 && (
					<div>
						<span className="text-slate-500">Amount:</span>{" "}
						<span className="font-medium text-slate-800">
							${approval.amount.toFixed(2)}
						</span>
					</div>
				)}
				<div className="col-span-2">
					<span className="text-slate-500">Reason:</span>{" "}
					<span className="text-slate-700">{approval.reason || "—"}</span>
				</div>
				{approval.decision_explanation && (
					<div className="col-span-2">
						<span className="text-slate-500">Agent Explanation:</span>
						<p className="text-slate-700 mt-0.5 text-xs leading-relaxed bg-amber-100/50 rounded-lg p-2">
							{approval.decision_explanation}
						</p>
					</div>
				)}
			</div>

			{/* Note input */}
			<div className="mb-4">
				<label
					htmlFor="approval-note"
					className="block text-xs font-medium text-slate-600 mb-1"
				>
					Note (optional)
				</label>
				<input
					id="approval-note"
					type="text"
					value={note}
					onChange={(e) => setNote(e.target.value)}
					placeholder="Add a note for this decision..."
					className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
					disabled={isSubmitting}
				/>
			</div>

			{/* Action buttons */}
			{!showConfirm ? (
				<div className="flex gap-3">
					<button
						type="button"
						onClick={() => setShowConfirm("approve")}
						disabled={isSubmitting}
						className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
					>
						<Check size={16} />
						Approve
					</button>
					<button
						type="button"
						onClick={() => setShowConfirm("reject")}
						disabled={isSubmitting}
						className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2 bg-white text-red-600 text-sm font-medium rounded-lg border border-red-200 hover:bg-red-50 disabled:opacity-50 transition-colors"
					>
						<X size={16} />
						Reject & Escalate
					</button>
				</div>
			) : (
				<div className="space-y-3">
					<p className="text-sm font-medium text-slate-700">
						Confirm {showConfirm === "approve" ? "approval" : "rejection"}?
					</p>
					<div className="flex gap-3">
						<button
							type="button"
							onClick={handleConfirm}
							disabled={isSubmitting}
							className={`flex-1 px-4 py-2 text-sm font-medium text-white rounded-lg disabled:opacity-50 transition-colors ${
								showConfirm === "approve"
									? "bg-green-600 hover:bg-green-700"
									: "bg-red-600 hover:bg-red-700"
							}`}
						>
							{isSubmitting ? "Processing..." : "Yes, confirm"}
						</button>
						<button
							type="button"
							onClick={() => setShowConfirm(null)}
							disabled={isSubmitting}
							className="flex-1 px-4 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 transition-colors"
						>
							Cancel
						</button>
					</div>
				</div>
			)}
		</div>
	);
}
