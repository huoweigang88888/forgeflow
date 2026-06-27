"use client";

import { useAuthStore } from "@/lib/auth-store";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

/**
 * Shopify OAuth Callback Page.
 *
 * Shopify redirects here after the merchant approves the app.
 *
 * Route: /auth/shopify/callback?code={}&shop={}&hmac={}&state={}&timestamp={}
 */
export default function ShopifyCallbackPage() {
	const { t } = useTranslation();

	return (
		<Suspense
			fallback={
				<div className="flex min-h-screen items-center justify-center bg-slate-50">
					<div className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg border border-slate-200 text-center">
						<div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
						<h1 className="text-lg font-semibold text-slate-800 mb-2">
							{t("auth.loading")}
						</h1>
					</div>
				</div>
			}
		>
			<ShopifyCallbackInner />
		</Suspense>
	);
}

function ShopifyCallbackInner() {
	const router = useRouter();
	const searchParams = useSearchParams();
	const { setToken } = useAuthStore();
	const { t } = useTranslation();

	const [status, setStatus] = useState<"connecting" | "error" | "done">(
		"connecting",
	);
	const [errorMessage, setErrorMessage] = useState("");

	useEffect(() => {
		const code = searchParams.get("code");
		const shop = searchParams.get("shop");
		const hmac = searchParams.get("hmac");
		const state = searchParams.get("state");
		const timestamp = searchParams.get("timestamp");

		// Validate required params
		if (!code || !shop || !hmac || !state) {
			setStatus("error");
			setErrorMessage(t("auth.missingParams"));
			return;
		}

		// Build callback URL for the backend
		const params = new URLSearchParams({
			code,
			shop,
			hmac,
			state,
			timestamp: timestamp || "",
		});

		const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

		fetch(`${API_BASE}/api/v1/auth/shopify/callback?${params.toString()}`)
			.then(async (response) => {
				if (!response.ok) {
					const errData = await response.json().catch(() => ({}));
					throw new Error(
						errData.detail?.error_description ||
							errData.message ||
							t("auth.failedToConnect"),
					);
				}
				return response.json();
			})
			.then((data) => {
				const { access_token, shop_domain } = data.data;
				// Store the ForgeFlow JWT
				setToken(access_token, shop_domain);
				setStatus("done");

				// Redirect to settings page after a brief delay
				setTimeout(() => {
					router.push("/dashboard/settings");
				}, 1500);
			})
			.catch((err) => {
				setStatus("error");
				setErrorMessage(err.message || t("auth.unexpectedError"));
			});
	}, [searchParams, router, setToken, t]);

	return (
		<div className="flex min-h-screen items-center justify-center bg-slate-50">
			<div className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg border border-slate-200 text-center">
				{status === "connecting" && (
					<>
						<div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-indigo-200 border-t-indigo-600" />
						<h1 className="text-lg font-semibold text-slate-800 mb-2">
							{t("auth.connecting")}
						</h1>
						<p className="text-sm text-slate-500">{t("auth.connectingDesc")}</p>
					</>
				)}

				{status === "done" && (
					<>
						<div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
							<svg
								className="h-6 w-6 text-green-600"
								fill="none"
								viewBox="0 0 24 24"
								strokeWidth={2}
								stroke="currentColor"
								aria-hidden="true"
							>
								<title>{t("auth.success")}</title>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									d="M4.5 12.75l6 6 9-13.5"
								/>
							</svg>
						</div>
						<h1 className="text-lg font-semibold text-slate-800 mb-2">
							{t("auth.connected")}
						</h1>
						<p className="text-sm text-slate-500">{t("auth.redirecting")}</p>
					</>
				)}

				{status === "error" && (
					<>
						<div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-red-100">
							<svg
								className="h-6 w-6 text-red-600"
								fill="none"
								viewBox="0 0 24 24"
								strokeWidth={2}
								stroke="currentColor"
							>
								<title>{t("auth.error")}</title>
								<path
									strokeLinecap="round"
									strokeLinejoin="round"
									d="M6 18L18 6M6 6l12 12"
								/>
							</svg>
						</div>
						<h1 className="text-lg font-semibold text-slate-800 mb-2">
							{t("auth.connectionFailed")}
						</h1>
						<p className="text-sm text-red-600 mb-4">{errorMessage}</p>
						<button
							type="button"
							onClick={() => router.push("/dashboard/settings")}
							className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
						>
							{t("auth.backToSettings")}
						</button>
					</>
				)}
			</div>
		</div>
	);
}
