"use client";

import Link from "next/link";
import { useTranslation } from "react-i18next";

export default function HomePage() {
	const { t } = useTranslation();

	return (
		<main className="flex min-h-screen flex-col items-center justify-center p-8">
			<div className="max-w-2xl text-center">
				<h1 className="mb-4 text-5xl font-bold tracking-tight text-brand-600">
					{t("home.title")}
				</h1>
				<p className="mb-2 text-xl text-slate-600">{t("home.subtitle")}</p>
				<p className="mb-8 text-slate-400">{t("home.description")}</p>
				<div className="flex gap-4 justify-center">
					<Link
						href="/dashboard"
						className="rounded-lg bg-brand-600 px-6 py-3 text-white hover:bg-brand-700 transition-colors"
					>
						{t("home.cta")}
					</Link>
				</div>
			</div>
		</main>
	);
}
