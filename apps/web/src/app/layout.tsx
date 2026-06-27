import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { I18nProvider } from "@/lib/i18n";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
	title: "ForgeFlow AI — After-Sales Workforce",
	description:
		"AI-powered after-sales service automation for e-commerce. Automate 80% of support tickets.",
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html lang="en" suppressHydrationWarning>
			<body className={inter.className}>
				<I18nProvider>
					<Providers>{children}</Providers>
				</I18nProvider>
			</body>
		</html>
	);
}
