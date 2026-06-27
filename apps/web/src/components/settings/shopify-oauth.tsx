"use client";

import { useAuthStore } from "@/lib/auth-store";
import { useState } from "react";
import { useTranslation } from "react-i18next";

/**
 * Shopify OAuth connection component.
 *
 * Renders in the Settings page. When no store is connected, shows an input
 * for the shop domain and a "Connect" button. When connected, shows the
 * store domain with a green indicator and a "Disconnect" button.
 */
export default function ShopifyOAuth() {
	const {
		token,
		shopDomain,
		isConnecting,
		setToken,
		clearToken,
		setConnecting,
	} = useAuthStore();
	const [shopInput, setShopInput] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [disconnecting, setDisconnecting] = useState(false);
	const { t } = useTranslation();

	const isConnected = !!token && !!shopDomain;

	/** Initiate OAuth flow: redirect to backend install endpoint */
	const handleConnect = () => {
		const domain = shopInput.trim();
		if (!domain) {
			setError(t("shopify.enterDomain"));
			return;
		}
		if (!domain.endsWith(".myshopify.com")) {
			setError(t("shopify.invalidDomain"));
			return;
		}

		setError(null);
		setConnecting(true);

		// Redirect to backend OAuth install endpoint
		// The backend will 302 redirect to Shopify's OAuth authorization page
		window.location.href = `http://localhost:8000/api/v1/auth/shopify/install?shop=${encodeURIComponent(domain)}`;
	};

	/** Disconnect: call backend to delete session, then clear local state */
	const handleDisconnect = async () => {
		if (!window.confirm(t("shopify.confirmDisconnect"))) {
			return;
		}

		setDisconnecting(true);
		setError(null);

		try {
			const API_BASE =
				process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
			const response = await fetch(`${API_BASE}/api/v1/auth/session`, {
				method: "DELETE",
				headers: {
					Authorization: `Bearer ${token}`,
					"Content-Type": "application/json",
				},
			});

			if (!response.ok) {
				const data = await response.json().catch(() => ({}));
				throw new Error(data.message || t("shopify.failedDisconnect"));
			}

			clearToken();
			setShopInput("");
		} catch (err) {
			setError(
				err instanceof Error ? err.message : t("shopify.disconnectFailed"),
			);
		} finally {
			setDisconnecting(false);
		}
	};

	return (
		<div className="space-y-4">
			{isConnected ? (
				/* ── Connected State ── */
				<div className="flex items-center justify-between p-4 bg-green-50 rounded-lg border border-green-200">
					<div className="flex items-center gap-3">
						<span className="flex h-3 w-3">
							<span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75" />
							<span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
						</span>
						<div>
							<p className="text-sm font-medium text-green-800">
								{t("shopify.connected", { domain: shopDomain })}
							</p>
							<p className="text-xs text-green-600">
								{t("shopify.tokenActive")}
							</p>
						</div>
					</div>
					<button
						type="button"
						onClick={handleDisconnect}
						disabled={disconnecting}
						className="rounded-lg border border-red-300 px-4 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 transition-colors disabled:opacity-50"
					>
						{disconnecting
							? t("shopify.disconnecting")
							: t("shopify.disconnect")}
					</button>
				</div>
			) : (
				/* ── Not Connected — Store Domain Input ── */
				<div className="space-y-3">
					<div>
						<label
							htmlFor="shopify-domain-oauth"
							className="block text-sm font-medium text-slate-700 mb-1"
						>
							{t("shopify.storeDomain")}
						</label>
						<div className="flex gap-3 max-w-md">
							<input
								id="shopify-domain-oauth"
								type="text"
								placeholder={t("shopify.storeDomainPlaceholder")}
								value={shopInput}
								onChange={(e) => {
									setShopInput(e.target.value);
									setError(null);
								}}
								onKeyDown={(e) => {
									if (e.key === "Enter") handleConnect();
								}}
								className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
							/>
							<button
								type="button"
								onClick={handleConnect}
								disabled={isConnecting}
								className="rounded-lg bg-indigo-600 px-6 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors disabled:opacity-50 whitespace-nowrap"
							>
								{isConnecting
									? t("shopify.connecting")
									: t("shopify.connectStore")}
							</button>
						</div>
						<p className="mt-1 text-xs text-slate-400">
							{t("shopify.redirectHelper")}
						</p>
					</div>
				</div>
			)}

			{/* Error display */}
			{error && (
				<div className="p-3 bg-red-50 border border-red-200 rounded-lg">
					<p className="text-sm text-red-700">{error}</p>
				</div>
			)}
		</div>
	);
}
