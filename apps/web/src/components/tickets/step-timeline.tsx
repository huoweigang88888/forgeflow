"use client";

import type { StepName, StepStatus } from "@/types";
import { CheckCircle2, Circle, Clock, XCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

interface StepTimelineProps {
	steps: { step: string; status: string; result: string | null }[];
	progress: number;
}

function StepIcon({ status }: { status: StepStatus | string }) {
	switch (status) {
		case "done":
			return <CheckCircle2 size={18} className="text-green-500" />;
		case "failed":
			return <XCircle size={18} className="text-red-500" />;
		case "skipped":
			return <Circle size={18} className="text-slate-300" />;
		default:
			return <Clock size={18} className="text-slate-300" />;
	}
}

export function StepTimeline({ steps, progress }: StepTimelineProps) {
	const { t } = useTranslation();

	const getStepLabel = (step: string): string => {
		const keyMap: Record<string, string> = {
			detect_intent: "steps.detectIntent",
			lookup_order: "steps.lookupOrder",
			check_logistics: "steps.checkLogistics",
			check_policy: "steps.checkPolicy",
			make_decision: "steps.makeDecision",
			execute: "steps.execute",
		};
		return t(keyMap[step] ?? step);
	};

	if (!steps || steps.length === 0) {
		return (
			<div className="bg-white rounded-xl border border-slate-200 p-5 text-center">
				<p className="text-sm text-slate-400">{t("steps.waitingForAgent")}</p>
			</div>
		);
	}

	return (
		<div className="bg-white rounded-xl border border-slate-200 p-5">
			<div className="flex items-center justify-between mb-4">
				<h3 className="text-sm font-semibold text-slate-700">
					{t("steps.processingSteps")}
				</h3>
				<span className="text-xs text-slate-400">
					{t("steps.percentComplete", { n: Math.round(progress * 100) })}
				</span>
			</div>

			{/* Progress bar */}
			<div className="w-full bg-slate-100 rounded-full h-2 mb-5">
				<div
					className="bg-brand-500 h-2 rounded-full transition-all duration-500"
					style={{ width: `${Math.round(progress * 100)}%` }}
				/>
			</div>

			{/* Step list */}
			<div className="space-y-0">
				{steps.map((s, i) => {
					const isLast = i === steps.length - 1;
					return (
						<div key={s.step} className="flex gap-3">
							{/* Connector line + icon */}
							<div className="flex flex-col items-center">
								<StepIcon status={s.status} />
								{!isLast && (
									<div
										className={`w-0.5 flex-1 min-h-[24px] ${
											s.status === "done" ? "bg-green-200" : "bg-slate-200"
										}`}
									/>
								)}
							</div>

							{/* Content */}
							<div className={`pb-4 ${isLast ? "" : ""}`}>
								<p
									className={`text-sm font-medium ${
										s.status === "done"
											? "text-slate-900"
											: s.status === "failed"
												? "text-red-700"
												: "text-slate-400"
									}`}
								>
									{getStepLabel(s.step)}
								</p>
								{s.result && (
									<p className="text-xs text-slate-500 mt-0.5">{s.result}</p>
								)}
							</div>
						</div>
					);
				})}
			</div>
		</div>
	);
}
