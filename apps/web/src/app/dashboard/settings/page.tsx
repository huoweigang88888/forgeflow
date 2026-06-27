"use client";

import ShopifyOAuth from "@/components/settings/shopify-oauth";
import { useAuthStore } from "@/lib/auth-store";
import { useState } from "react";
import { useTranslation } from "react-i18next";

export default function SettingsPage() {
	const [autoRefundThreshold, setAutoRefundThreshold] = useState("50");
	const [platform, setPlatform] = useState("mock");
	const [saved, setSaved] = useState(false);
	const { token, shopDomain } = useAuthStore();
	const isAuthenticated = !!token && !!shopDomain;
	const { t } = useTranslation();

	const handleSave = () => {
		setSaved(true);
		setTimeout(() => setSaved(false), 2000);
	};

	return (
		<div>
			<h1 className="text-2xl font-bold text-slate-900 mb-2">
				{t("settings.title")}
			</h1>
			<p className="text-slate-500 mb-8">{t("settings.subtitle")}</p>

			{/* Shopify Connection (OAuth) */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					{t("settings.storeConnection")}
				</h2>
				<ShopifyOAuth />
			</section>

			{/* Store Configuration */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					{t("settings.storeConfiguration")}
				</h2>
				<div className="space-y-4">
					<div>
						<label
							htmlFor="platform-select"
							className="block text-sm font-medium text-slate-700 mb-1"
						>
							{t("settings.platform")}
						</label>
						<select
							id="platform-select"
							value={platform}
							onChange={(e) => setPlatform(e.target.value)}
							className="w-full max-w-md rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
						>
							<option value="mock">{t("settings.mockTesting")}</option>
							<option value="shopify">{t("settings.shopifyLive")}</option>
						</select>
					</div>
				</div>
			</section>

			{/* Automation Rules */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					{t("settings.automationRules")}
				</h2>
				<div className="space-y-4">
					<div>
						<label
							htmlFor="auto-refund-threshold"
							className="block text-sm font-medium text-slate-700 mb-1"
						>
							{t("settings.autoRefundThreshold")}
							<span className="text-slate-400 ml-2 font-normal">
								{t("settings.autoRefundHelper")}
							</span>
						</label>
						<input
							id="auto-refund-threshold"
							type="number"
							value={autoRefundThreshold}
							onChange={(e) => setAutoRefundThreshold(e.target.value)}
							min="0"
							step="1"
							className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
						/>
					</div>
					<div className="flex items-center gap-3">
						<input
							type="checkbox"
							id="auto_approve_vip"
							className="h-4 w-4 rounded"
							defaultChecked
						/>
						<label
							htmlFor="auto_approve_vip"
							className="text-sm text-slate-700"
						>
							{t("settings.autoApproveVip")}
						</label>
					</div>
					<div className="flex items-center gap-3">
						<input
							type="checkbox"
							id="approval_reminders"
							className="h-4 w-4 rounded"
							defaultChecked
						/>
						<label
							htmlFor="approval_reminders"
							className="text-sm text-slate-700"
						>
							{t("settings.sendReminders")}
						</label>
					</div>
				</div>
			</section>

			{/* Notification Settings */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					{t("settings.notifications")}
				</h2>
				<div className="space-y-3">
					<div className="flex items-center gap-3">
						<input
							type="checkbox"
							id="notify_refund"
							className="h-4 w-4 rounded"
							defaultChecked
						/>
						<label htmlFor="notify_refund" className="text-sm text-slate-700">
							{t("settings.notifyRefund")}
						</label>
					</div>
					<div className="flex items-center gap-3">
						<input
							type="checkbox"
							id="notify_escalation"
							className="h-4 w-4 rounded"
							defaultChecked
						/>
						<label
							htmlFor="notify_escalation"
							className="text-sm text-slate-700"
						>
							{t("settings.notifyEscalation")}
						</label>
					</div>
					<div className="flex items-center gap-3">
						<input
							type="checkbox"
							id="notify_approval"
							className="h-4 w-4 rounded"
							defaultChecked
						/>
						<label htmlFor="notify_approval" className="text-sm text-slate-700">
							{t("settings.notifyApproval")}
						</label>
					</div>
				</div>
			</section>

			{/* API Connection Status */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					{t("settings.apiConnection")}
				</h2>
				<div className="flex items-center gap-2">
					{isAuthenticated ? (
						<>
							<span className="flex h-3 w-3">
								<span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75" />
								<span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
							</span>
							<span className="text-sm text-green-700 font-medium">
								{t("settings.authenticated", { shopDomain })}
							</span>
						</>
					) : (
						<>
							<span className="flex h-3 w-3">
								<span className="relative inline-flex rounded-full h-3 w-3 bg-yellow-500" />
							</span>
							<span className="text-sm text-slate-500 font-medium">
								{t("settings.notConnected")}
							</span>
						</>
					)}
					<span className="text-xs text-slate-400 ml-2">
						{t("settings.apiStatus")}
					</span>
				</div>
			</section>

			{/* Save Button */}
			<div className="flex items-center gap-4">
				<button
					type="button"
					onClick={handleSave}
					className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
				>
					{saved ? t("settings.saved") : t("settings.saveSettings")}
				</button>
			</div>
		</div>
	);
}
