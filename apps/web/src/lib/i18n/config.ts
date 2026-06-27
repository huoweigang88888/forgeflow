"use client";

import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import zh from "./locales/zh.json";

// Prevent re-init in hot reload
if (!i18n.isInitialized) {
	i18n
		.use(LanguageDetector)
		.use(initReactI18next)
		.init({
			resources: {
				en: { translation: en },
				zh: { translation: zh },
			},
			fallbackLng: "en",
			supportedLngs: ["en", "zh"],
			nonExplicitSupportedLngs: true,
			debug: false,
			interpolation: {
				escapeValue: false, // React already escapes
			},
			detection: {
				order: ["localStorage", "navigator"],
				lookupLocalStorage: "forgeflow.language",
				caches: ["localStorage"],
				convertDetectedLanguage: (lng: string) => {
					// Map zh-CN, zh-TW, zh-HK etc. to zh
					if (lng.startsWith("zh")) return "zh";
					return lng;
				},
			},
		});
}

export default i18n;
