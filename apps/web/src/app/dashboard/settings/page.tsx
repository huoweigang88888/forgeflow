"use client";

import ShopifyOAuth from "@/components/settings/shopify-oauth";
import { useAuthStore } from "@/lib/auth-store";
import { useState } from "react";

export default function SettingsPage() {
	const [autoRefundThreshold, setAutoRefundThreshold] = useState("50");
	const [platform, setPlatform] = useState("mock");
	const [saved, setSaved] = useState(false);
	const { token, shopDomain } = useAuthStore();
	const isAuthenticated = !!token && !!shopDomain;

	const handleSave = () => {
		setSaved(true);
		setTimeout(() => setSaved(false), 2000);
	};

	return (
		<div>
			<h1 className="text-2xl font-bold text-slate-900 mb-2">Settings</h1>
			<p className="text-slate-500 mb-8">
				Configure your store, policies, and automation rules.
			</p>

			{/* Shopify Connection (OAuth) */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					Store Connection
				</h2>
				<ShopifyOAuth />
			</section>

			{/* Store Configuration */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					Store Configuration
				</h2>
				<div className="space-y-4">
					<div>
						<label
							htmlFor="platform-select"
							className="block text-sm font-medium text-slate-700 mb-1"
						>
							Platform
						</label>
						<select
							id="platform-select"
							value={platform}
							onChange={(e) => setPlatform(e.target.value)}
							className="w-full max-w-md rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
						>
							<option value="mock">Mock (Testing)</option>
							<option value="shopify">Shopify (Live)</option>
						</select>
					</div>
				</div>
			</section>

			{/* Automation Rules */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					Automation Rules
				</h2>
				<div className="space-y-4">
					<div>
						<label
							htmlFor="auto-refund-threshold"
							className="block text-sm font-medium text-slate-700 mb-1"
						>
							Auto-Refund Threshold (USD)
							<span className="text-slate-400 ml-2 font-normal">
								Orders below this amount are auto-refunded without approval
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
							Auto-approve refunds for VIP customers
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
							Send email reminders for pending approvals
						</label>
					</div>
				</div>
			</section>

			{/* Notification Settings */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					Notifications
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
							Send notification on automatic refund
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
							Send notification on ticket escalation
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
							Send notification on approval required
						</label>
					</div>
				</div>
			</section>

			{/* API Connection Status */}
			<section className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
				<h2 className="text-lg font-semibold text-slate-800 mb-4">
					API Connection
				</h2>
				<div className="flex items-center gap-2">
					{isAuthenticated ? (
						<>
							<span className="flex h-3 w-3">
								<span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-green-400 opacity-75" />
								<span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
							</span>
							<span className="text-sm text-green-700 font-medium">
								Authenticated — {shopDomain}
							</span>
						</>
					) : (
						<>
							<span className="flex h-3 w-3">
								<span className="relative inline-flex rounded-full h-3 w-3 bg-yellow-500" />
							</span>
							<span className="text-sm text-slate-500 font-medium">
								Not connected — connect a Shopify store above
							</span>
						</>
					)}
					<span className="text-xs text-slate-400 ml-2">
						API: localhost:8000 | WS: localhost:8000/ws
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
					{saved ? "Saved ✓" : "Save Settings"}
				</button>
			</div>
		</div>
	);
}
