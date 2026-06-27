"use client";

import { Component, type ReactNode } from "react";
import { getI18n } from "react-i18next";

interface ErrorBoundaryProps {
	children: ReactNode;
	fallback?: ReactNode;
}

interface ErrorBoundaryState {
	hasError: boolean;
	error: Error | null;
}

// Helper to access i18n outside a component (ErrorBoundary is a class)
function getT() {
	try {
		const i18n = getI18n();
		return i18n.t.bind(i18n);
	} catch {
		return (key: string) => key;
	}
}

export class ErrorBoundary extends Component<
	ErrorBoundaryProps,
	ErrorBoundaryState
> {
	constructor(props: ErrorBoundaryProps) {
		super(props);
		this.state = { hasError: false, error: null };
	}

	static getDerivedStateFromError(error: Error): ErrorBoundaryState {
		return { hasError: true, error };
	}

	render() {
		const t = getT();

		if (this.state.hasError) {
			if (this.props.fallback) {
				return this.props.fallback;
			}

			return (
				<div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
					<div className="text-red-500 text-lg font-semibold mb-2">
						{t("errors.somethingWentWrong")}
					</div>
					<p className="text-red-400 text-sm mb-4">
						{this.state.error?.message || t("errors.unexpectedError")}
					</p>
					<button
						type="button"
						onClick={() => this.setState({ hasError: false, error: null })}
						className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
					>
						{t("errors.tryAgain")}
					</button>
				</div>
			);
		}

		return this.props.children;
	}
}
