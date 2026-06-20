export function SkeletonCard({ className = "" }: { className?: string }) {
	return (
		<div
			className={`animate-pulse rounded-xl border border-slate-200 bg-white p-6 ${className}`}
		>
			<div className="h-4 w-24 rounded bg-slate-200 mb-3" />
			<div className="h-6 w-32 rounded bg-slate-200 mb-2" />
			<div className="h-3 w-48 rounded bg-slate-100" />
		</div>
	);
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
	return (
		<div className="space-y-3">
			{Array.from({ length: rows }).map((_, i) => (
				<div
					// biome-ignore lint/suspicious/noArrayIndexKey: static skeleton placeholder
					key={`skel-${rows}-${i}`}
					className="animate-pulse flex items-center gap-4 rounded-lg border border-slate-200 bg-white p-4"
				>
					<div className="h-4 w-20 rounded bg-slate-200" />
					<div className="h-4 w-32 rounded bg-slate-200" />
					<div className="h-4 w-24 rounded bg-slate-200" />
					<div className="h-4 w-16 rounded bg-slate-200" />
					<div className="ml-auto h-4 w-12 rounded bg-slate-100" />
				</div>
			))}
		</div>
	);
}

export function SkeletonDetail() {
	return (
		<div className="animate-pulse space-y-6">
			<div className="flex items-center gap-4">
				<div className="h-8 w-48 rounded bg-slate-200" />
				<div className="h-6 w-20 rounded-full bg-slate-200" />
			</div>
			<div className="grid grid-cols-2 gap-4">
				{[1, 2, 3, 4].map((i) => (
					<div key={i} className="rounded-lg border border-slate-200 p-4">
						<div className="h-3 w-16 rounded bg-slate-200 mb-2" />
						<div className="h-5 w-24 rounded bg-slate-200" />
					</div>
				))}
			</div>
			<div className="space-y-3">
				{[1, 2, 3].map((i) => (
					<div key={i} className="h-12 w-full rounded-lg bg-slate-100" />
				))}
			</div>
		</div>
	);
}
