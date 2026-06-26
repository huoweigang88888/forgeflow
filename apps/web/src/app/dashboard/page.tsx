"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, Inbox, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { LLMCostChart } from "@/components/dashboard/llm-cost-chart";
import { ProcessingRateChart } from "@/components/dashboard/processing-rate-chart";
import { StatsCard } from "@/components/dashboard/stats-card";
import { TrendLineChart } from "@/components/dashboard/trend-line-chart";
import {
	getDashboardStats,
	getTicketMetrics,
	listTickets,
} from "@/lib/tickets";
import type { TicketListItem, TicketStatus } from "@/types";

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

export default function DashboardPage() {
	const [trendDays, setTrendDays] = useState(30);

	const { data: stats, isLoading: statsLoading } = useQuery({
		queryKey: ["dashboard-stats"],
		queryFn: getDashboardStats,
		refetchInterval: 30_000,
	});

	const { data: metrics, isLoading: metricsLoading } = useQuery({
		queryKey: ["dashboard-metrics", trendDays],
		queryFn: () => getTicketMetrics(trendDays),
		refetchInterval: 60_000,
	});

	const { data: recent, isLoading: recentLoading } = useQuery({
		queryKey: ["recent-tickets"],
		queryFn: () => listTickets({ page: 1, page_size: 5 }),
	});

	const isLoading = statsLoading || recentLoading;

	return (
		<div>
			<div className="flex items-center justify-between mb-2">
				<h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
				<Link
					href="/dashboard/tickets"
					className="text-sm text-brand-600 hover:text-brand-700 font-medium"
				>
					View all tickets →
				</Link>
			</div>
			<p className="text-slate-500 mb-8">
				After-sales automation overview for your store.
			</p>

			{/* Stats Grid */}
			<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
				<StatsCard
					label="Total Tickets"
					value={isLoading ? "—" : (stats?.total_tickets ?? 0)}
					subtext="All time"
					icon={Inbox}
				/>
				<StatsCard
					label="Auto-Resolved"
					value={isLoading ? "—" : (stats?.resolved ?? 0)}
					subtext={
						stats ? `${stats.auto_resolution_rate}% resolution rate` : undefined
					}
					icon={CheckCircle2}
					trend="up"
				/>
				<StatsCard
					label="Pending Approval"
					value={isLoading ? "—" : (stats?.pending_approval ?? 0)}
					subtext="Needs review"
					icon={Clock}
					trend={stats && stats.pending_approval > 0 ? "down" : "neutral"}
				/>
				<StatsCard
					label="Avg. Time"
					value={
						isLoading
							? "—"
							: stats
								? `${(stats.avg_processing_time_ms / 1000).toFixed(1)}s`
								: "—"
					}
					subtext="Per ticket"
					icon={TrendingUp}
				/>
			</div>

			{/* SLA Compliance Card */}
			{metrics && (
				<div className="bg-white rounded-xl border border-slate-200 p-5 mb-8">
					<div className="flex items-center justify-between">
						<div>
							<h3 className="text-sm font-semibold text-slate-700">
								SLA Compliance Rate
							</h3>
							<p className="text-xs text-slate-400 mt-0.5">
								% of resolved tickets within SLA deadline
							</p>
						</div>
						<span className="text-2xl font-bold text-brand-600">
							{metrics.sla_compliance_rate}%
						</span>
					</div>
				</div>
			)}

			{/* Resolution Rate Bar */}
			{stats && stats.total_tickets > 0 && (
				<div className="bg-white rounded-xl border border-slate-200 p-5 mb-8">
					<div className="flex items-center justify-between mb-3">
						<h3 className="text-sm font-semibold text-slate-700">
							Auto-Resolution Rate
						</h3>
						<span className="text-sm font-bold text-brand-600">
							{stats.auto_resolution_rate}%
						</span>
					</div>
					<div className="w-full bg-slate-100 rounded-full h-3">
						<div
							className="bg-brand-500 h-3 rounded-full transition-all duration-700"
							style={{ width: `${Math.min(stats.auto_resolution_rate, 100)}%` }}
						/>
					</div>
					<div className="flex justify-between mt-2 text-xs text-slate-400">
						<span>
							{stats.resolved} of {stats.total_tickets} resolved
						</span>
						<span>
							{stats.escalated} escalated · {stats.failed} failed
						</span>
					</div>
				</div>
			)}

			{/* Charts Row 1 — Processing Rate + LLM Cost */}
			<div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
				<div className="lg:col-span-1">
					<ProcessingRateChart data={metrics?.processing_rate ?? []} />
				</div>
				<div className="lg:col-span-2">
					<LLMCostChart data={metrics?.llm_cost_daily ?? []} />
				</div>
			</div>

			{/* Charts Row 2 — Auto-Resolve Trend */}
			<div className="mb-8">
				<TrendLineChart
					data={metrics?.auto_resolve_trend ?? []}
					days={trendDays}
					onDaysChange={setTrendDays}
				/>
			</div>

			{/* Recent Tickets */}
			<div className="bg-white rounded-xl border border-slate-200">
				<div className="px-5 py-4 border-b border-slate-100">
					<h3 className="text-sm font-semibold text-slate-700">
						Recent Tickets
					</h3>
				</div>
				{recentLoading ? (
					<div className="p-8 text-center">
						<p className="text-slate-400">Loading...</p>
					</div>
				) : !recent || recent.tickets.length === 0 ? (
					<div className="p-8 text-center">
						<Inbox size={32} className="mx-auto text-slate-300 mb-3" />
						<p className="text-slate-400">No tickets yet.</p>
						<p className="text-xs text-slate-300 mt-1">
							Create a ticket via the API to see it here.
						</p>
					</div>
				) : (
					<div className="divide-y divide-slate-50">
						{recent.tickets.map((ticket: TicketListItem) => (
							<Link
								key={ticket.ticket_id}
								href={`/dashboard/tickets/${ticket.ticket_id}`}
								className="flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors"
							>
								<div className="flex-1 min-w-0">
									<div className="flex items-center gap-2">
										<span className="text-sm font-mono text-slate-500 truncate">
											{ticket.ticket_id}
										</span>
										<span
											className={`text-xs px-2 py-0.5 rounded-full font-medium ${
												STATUS_COLORS[ticket.status]
											}`}
										>
											{STATUS_LABELS[ticket.status]}
										</span>
									</div>
									<p className="text-sm text-slate-600 truncate mt-0.5">
										{ticket.issue_text?.slice(0, 80)}
										{(ticket.issue_text?.length ?? 0) > 80 ? "…" : ""}
									</p>
								</div>
								<span className="text-xs text-slate-400 ml-4 shrink-0">
									{ticket.created_at
										? new Date(ticket.created_at).toLocaleDateString()
										: ""}
								</span>
							</Link>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
