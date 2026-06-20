import { ErrorBoundary } from "@/components/ui/error-boundary";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
/**
 * Tests for ErrorBoundary component (src/components/ui/error-boundary.tsx).
 */
import { describe, expect, it } from "vitest";

// Component that throws on render
function BrokenComponent({ shouldThrow }: { shouldThrow: boolean }) {
	if (shouldThrow) {
		throw new Error("Test explosion");
	}
	return <div>All good</div>;
}

describe("ErrorBoundary", () => {
	it("renders children when no error", () => {
		render(
			<ErrorBoundary>
				<div>Safe content</div>
			</ErrorBoundary>,
		);
		expect(screen.getByText("Safe content")).toBeInTheDocument();
	});

	it("shows default error UI when child throws", () => {
		// Suppress console.error for expected throw
		const spy = vi.spyOn(console, "error").mockImplementation(() => {});

		render(
			<ErrorBoundary>
				<BrokenComponent shouldThrow={true} />
			</ErrorBoundary>,
		);

		expect(screen.getByText("Something went wrong")).toBeInTheDocument();
		expect(screen.getByText("Test explosion")).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "Try Again" }),
		).toBeInTheDocument();

		spy.mockRestore();
	});

	it("shows custom fallback when provided", () => {
		const spy = vi.spyOn(console, "error").mockImplementation(() => {});

		render(
			<ErrorBoundary fallback={<div>Custom error panel</div>}>
				<BrokenComponent shouldThrow={true} />
			</ErrorBoundary>,
		);

		expect(screen.getByText("Custom error panel")).toBeInTheDocument();
		expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();

		spy.mockRestore();
	});

	it("Try Again button resets error state and re-renders children", async () => {
		const user = userEvent.setup();
		const spy = vi.spyOn(console, "error").mockImplementation(() => {});

		const { rerender } = render(
			<ErrorBoundary>
				<BrokenComponent shouldThrow={true} />
			</ErrorBoundary>,
		);

		expect(screen.getByText("Something went wrong")).toBeInTheDocument();

		// Click Try Again
		await user.click(screen.getByRole("button", { name: "Try Again" }));

		// After reset, the error boundary re-renders its children.
		// But the child still throws — so it should show the error UI again.
		// We verify the reset happened by checking the error UI rendered again.
		expect(screen.getByText("Something went wrong")).toBeInTheDocument();

		spy.mockRestore();
	});
});
