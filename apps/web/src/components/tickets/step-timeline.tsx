"use client";

import type { StepName, StepStatus } from "@/types";
import { CheckCircle2, Circle, Clock, XCircle } from "lucide-react";

const STEP_LABELS: Record<StepName, string> = {
	detect_intent: "Detect Intent",
	lookup_order: "Lookup Order",
	check_logistics: "Check Logistics",
	check_policy: "Check Policy",
	make_decision: "Make Decision",
	execute: "Execute",
};

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
	if (!steps || steps.length === 0) {
		return (
			<div className="bg-white rounded-xl border border-slate-200 p-5 text-center">
				<p className="text-sm text-slate-400">Waiting for agent to start...</p>
			</div>
		);
	}

	return (
		<div className="bg-white rounded-xl border border-slate-200 p-5">
			<div className="flex items-center justify-between mb-4">
				<h3 className="text-sm font-semibold text-slate-700">
					Processing Steps
				</h3>
				<span className="text-xs text-slate-400">
					{Math.round(progress * 100)}% complete
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
									{STEP_LABELS[s.step as StepName] ?? s.step}
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
