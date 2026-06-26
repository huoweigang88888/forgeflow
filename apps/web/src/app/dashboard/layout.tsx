"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function DashboardLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	const pathname = usePathname();

	return (
		<div className="flex h-screen bg-slate-50">
			{/* Sidebar */}
			<aside className="w-64 bg-white border-r border-slate-200 p-4 flex flex-col">
				<div className="mb-8">
					<Link href="/" className="text-xl font-bold text-brand-600">
						ForgeFlow
					</Link>
					<p className="text-xs text-slate-400 mt-1">AI After-Sales</p>
				</div>
				<nav className="flex flex-col gap-1 flex-1">
					<NavItem
						href="/dashboard"
						label="Dashboard"
						active={pathname === "/dashboard"}
					/>
					<NavItem
						href="/dashboard/tickets"
						label="Tickets"
						active={pathname.startsWith("/dashboard/tickets")}
					/>
					<NavItem
						href="/dashboard/approvals"
						label="Approvals"
						active={pathname === "/dashboard/approvals"}
					/>
					<NavItem
						href="/dashboard/knowledge-base"
						label="Knowledge Base"
						active={pathname.startsWith("/dashboard/knowledge-base")}
					/>
					<NavItem
						href="/dashboard/settings"
						label="Settings"
						active={pathname === "/dashboard/settings"}
					/>
				</nav>
				<div className="text-xs text-slate-400 pt-4 border-t border-slate-100">
					Phase 2 — Frontend &amp; Approvals
				</div>
			</aside>

			{/* Main Content */}
			<main className="flex-1 overflow-auto p-8">{children}</main>
		</div>
	);
}

function NavItem({
	href,
	label,
	active = false,
}: {
	href: string;
	label: string;
	active?: boolean;
}) {
	return (
		<Link
			href={href}
			className={`rounded-lg px-3 py-2 text-sm transition-colors ${
				active
					? "bg-brand-50 text-brand-700 font-medium"
					: "text-slate-600 hover:bg-slate-100"
			}`}
		>
			{label}
		</Link>
	);
}
