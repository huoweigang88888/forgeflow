"use client";

import { useTranslation } from "react-i18next";

export function LanguageSwitcher() {
	const { i18n } = useTranslation();
	const currentLang = i18n.language?.startsWith("zh") ? "zh" : "en";

	const toggle = () => {
		const next = currentLang === "zh" ? "en" : "zh";
		i18n.changeLanguage(next);
	};

	return (
		<button
			type="button"
			onClick={toggle}
			className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 transition-colors"
			title={currentLang === "zh" ? "Switch to English" : "切换到中文"}
		>
			<span className="text-base">{currentLang === "zh" ? "🌐" : "🌐"}</span>
			<span className="font-medium">
				{currentLang === "zh" ? "中文" : "English"}
			</span>
			<span className="ml-auto text-xs text-slate-400">
				{currentLang === "zh" ? "EN" : "中"}
			</span>
		</button>
	);
}
