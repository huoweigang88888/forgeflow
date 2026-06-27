"use client";

import { useEffect } from "react";
import { I18nextProvider } from "react-i18next";
import { useTranslation } from "react-i18next";
import i18n from "./config";

function LangSync() {
	const { i18n } = useTranslation();

	useEffect(() => {
		document.documentElement.lang = i18n.language;
	}, [i18n.language]);

	return null;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
	return (
		<I18nextProvider i18n={i18n}>
			<LangSync />
			{children}
		</I18nextProvider>
	);
}
