"use client";

import { AlertTriangle, Check, X } from "lucide-react";
import { useState } from "react";
import type { PendingApproval } from "@/types";

interface ApprovalPanelProps {
	approval: PendingApproval;
	onApprove: (note: string) => Promise<void>;
	onReject: (note: string) => Promise<void>;
	isSubmitting: boolean;
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
