"use client";

import { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
	children: ReactNode;
	fallback?: ReactNode;
}

interface ErrorBoundaryState {
	hasError: boolean;
	error: Error | null;
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
		if (this.state.hasError) {
			if (this.props.fallback) {
				return this.props.fallback;
			}

			return (
				<div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
					<div className="text-red-500 text-lg font-semibold mb-2">
						Something went wrong
					</div>
					<p className="text-red-400 text-sm mb-4">
						{this.state.error?.message || "An unexpected error occurred"}
					</p>
					<button
						type="button"
						onClick={() => this.setState({ hasError: false, error: null })}
						className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
					>
						Try Again
					</button>
				</div>
			);
		}

		return this.props.children;
	}
}
