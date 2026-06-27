"use client";

import { LanguageSwitcher } from "@/lib/i18n";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslation } from "react-i18next";

export default function DashboardLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	const pathname = usePathname();
	const { t } = useTranslation();

	return (
		<div className="flex h-screen bg-slate-50">
			{/* Sidebar */}
			<aside className="w-64 bg-white border-r border-slate-200 p-4 flex flex-col">
				<div className="mb-8">
					<Link href="/" className="text-xl font-bold text-brand-600">
						{t("nav.brand")}
					</Link>
					<p className="text-xs text-slate-400 mt-1">{t("nav.tagline")}</p>
				</div>
				<nav className="flex flex-col gap-1 flex-1">
					<NavItem
						href="/dashboard"
						label={t("nav.dashboard")}
						active={pathname === "/dashboard"}
					/>
					<NavItem
						href="/dashboard/tickets"
						label={t("nav.tickets")}
						active={pathname.startsWith("/dashboard/tickets")}
					/>
					<NavItem
						href="/dashboard/approvals"
						label={t("nav.approvals")}
						active={pathname === "/dashboard/approvals"}
					/>
					<NavItem
						href="/dashboard/knowledge-base"
						label={t("nav.knowledgeBase")}
						active={pathname.startsWith("/dashboard/knowledge-base")}
					/>
					<NavItem
						href="/dashboard/settings"
						label={t("nav.settings")}
						active={pathname === "/dashboard/settings"}
					/>
				</nav>

				{/* Language Switcher */}
				<div className="mb-4">
					<LanguageSwitcher />
				</div>

				<div className="text-xs text-slate-400 pt-4 border-t border-slate-100">
					{t("nav.footer")}
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
