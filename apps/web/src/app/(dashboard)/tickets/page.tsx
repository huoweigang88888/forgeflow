"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { FilterBar } from "@/components/tickets/filter-bar";
import { TicketTable } from "@/components/tickets/ticket-table";
import { useTicketFilterStore } from "@/lib/store";
import { listTickets } from "@/lib/tickets";

export default function TicketsPage() {
	const { status, platform, page, pageSize, setStatus, setPlatform, setPage } = useTicketFilterStore();

	const { data, isLoading } = useQuery({
		queryKey: ["tickets", { page, pageSize, status, platform }],
		queryFn: () =>
			listTickets({
				page,
				page_size: pageSize,
				status: status === "all" ? undefined : status,
				platform: platform === "all" ? undefined : platform,
			}),
	});

	const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

	return (
		<div>
			<h1 className="text-2xl font-bold text-slate-900 mb-2">Tickets</h1>
			<p className="text-slate-500 mb-6">
				View and manage after-sales support tickets.
			</p>

			{/* Filters */}
			<div className="mb-4">
				<FilterBar
					current={status}
					onChange={setStatus}
					platform={platform}
					onPlatformChange={setPlatform}
				/>
			</div>

			{/* Table */}
			<TicketTable tickets={data?.tickets ?? []} isLoading={isLoading} />

			{/* Pagination */}
			{totalPages > 1 && (
				<div className="flex items-center justify-between mt-4">
					<p className="text-sm text-slate-500">
						{data?.total ?? 0} tickets total · Page {page} of {totalPages}
					</p>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() => setPage(Math.max(1, page - 1))}
							disabled={page <= 1}
							className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm border border-slate-200 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors"
						>
							<ChevronLeft size={14} />
							Previous
						</button>
						<button
							type="button"
							onClick={() => setPage(Math.min(totalPages, page + 1))}
							disabled={page >= totalPages}
							className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm border border-slate-200 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors"
						>
							Next
							<ChevronRight size={14} />
						</button>
					</div>
				</div>
			)}
		</div>
	);
}
