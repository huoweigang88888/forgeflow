"use client";

import type { PolicyDocument } from "@/types";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

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
	const { t } = useTranslation();

	const categoryColors: Record<string, string> = {
		shipping: "bg-blue-100 text-blue-700",
		refund: "bg-amber-100 text-amber-700",
		exchange: "bg-purple-100 text-purple-700",
		general: "bg-slate-100 text-slate-700",
	};

	const categoryKey = policy.category || "general";
	const categoryClass = categoryColors[categoryKey] || categoryColors.general;

	const categoryLabelMap: Record<string, string> = {
		shipping: t("knowledgeBase.categoryShipping"),
		refund: t("knowledgeBase.categoryRefund"),
		exchange: t("knowledgeBase.categoryExchange"),
		general: t("knowledgeBase.categoryGeneral"),
	};
	const categoryLabel = categoryLabelMap[categoryKey] || categoryKey;

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
						<span className="text-red-400 font-medium">
							{t("knowledgeBase.inactive")}
						</span>
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
								{isDeleting ? t("knowledgeBase.deleting") : t("common.confirm")}
							</button>
							<button
								type="button"
								onClick={() => setConfirmDelete(false)}
								className="text-slate-400 hover:text-slate-600"
							>
								{t("common.cancel")}
							</button>
						</span>
					) : (
						<button
							type="button"
							onClick={() => setConfirmDelete(true)}
							className="text-slate-400 hover:text-red-500 transition-colors"
							title={t("common.delete")}
						>
							<Trash2 size={14} />
						</button>
					)}
				</div>
			</div>
		</div>
	);
}
