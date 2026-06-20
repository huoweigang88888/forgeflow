"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";
import type { PolicyDocument } from "@/types";

interface PolicyCardProps {
	policy: PolicyDocument;
	similarity?: number;
	onDelete: (id: string) => void;
	isDeleting: boolean;
}

export function PolicyCard({
	policy,
	similarity,
	onDelete,
	isDeleting,
}: PolicyCardProps) {
	const [confirmDelete, setConfirmDelete] = useState(false);

	const categoryColors: Record<string, string> = {
		shipping: "bg-blue-100 text-blue-700",
		refund: "bg-amber-100 text-amber-700",
		exchange: "bg-purple-100 text-purple-700",
		general: "bg-slate-100 text-slate-700",
	};

	const categoryLabel = policy.category || "general";
	const categoryClass = categoryColors[categoryLabel] || categoryColors.general;

	return (
		<div className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-sm transition-shadow">
			{/* Header */}
			<div className="flex items-start justify-between gap-3 mb-2">
				<h3 className="font-semibold text-slate-900 leading-snug line-clamp-2">
					{policy.title}
				</h3>
				<div className="flex items-center gap-2 shrink-0">
					{similarity !== undefined && (
						<span className="text-xs text-slate-400 font-mono">
							{(similarity * 100).toFixed(0)}%
						</span>
					)}
					<span
						className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${categoryClass}`}
					>
						{categoryLabel}
					</span>
				</div>
			</div>

			{/* Content preview */}
			<p className="text-sm text-slate-500 line-clamp-3 mb-3">
				{policy.content}
			</p>

			{/* Meta */}
			<div className="flex items-center justify-between text-xs text-slate-400">
				<span>
					{policy.uploaded_at
						? new Date(policy.uploaded_at).toLocaleDateString()
						: "—"}
				</span>

				<div className="flex items-center gap-2">
					{!policy.is_active && (
						<span className="text-red-400 font-medium">Inactive</span>
					)}
					{confirmDelete ? (
						<span className="flex items-center gap-1">
							<button
								type="button"
								onClick={() => {
									onDelete(policy.id);
									setConfirmDelete(false);
								}}
								disabled={isDeleting}
								className="text-red-600 hover:text-red-700 font-medium disabled:opacity-50"
							>
								{isDeleting ? "Deleting..." : "Confirm"}
							</button>
							<button
								type="button"
								onClick={() => setConfirmDelete(false)}
								className="text-slate-400 hover:text-slate-600"
							>
								Cancel
							</button>
						</span>
					) : (
						<button
							type="button"
							onClick={() => setConfirmDelete(true)}
							className="text-slate-400 hover:text-red-500 transition-colors"
							title="Delete policy"
						>
							<Trash2 size={14} />
						</button>
					)}
				</div>
			</div>
		</div>
	);
}
