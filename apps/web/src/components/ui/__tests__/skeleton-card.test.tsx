import {
	SkeletonCard,
	SkeletonDetail,
	SkeletonTable,
} from "@/components/ui/skeleton-card";
import { render } from "@testing-library/react";
/**
 * Tests for Skeleton components (src/components/ui/skeleton-card.tsx).
 */
import { describe, expect, it } from "vitest";

describe("SkeletonCard", () => {
	it("renders with default classes", () => {
		const { container } = render(<SkeletonCard />);
		const card = container.firstElementChild;
		expect(card).toBeInTheDocument();
		expect(card?.className).toContain("animate-pulse");
		expect(card?.className).toContain("rounded-xl");
	});

	it("merges additional className", () => {
		const { container } = render(<SkeletonCard className="extra-custom" />);
		const card = container.firstElementChild;
		expect(card).toBeInTheDocument();
		expect(card?.className).toContain("extra-custom");
		expect(card?.className).toContain("animate-pulse");
	});
});

describe("SkeletonTable", () => {
	it("renders default 5 rows", () => {
		const { container } = render(<SkeletonTable />);
		const rows = container.querySelectorAll(".flex.items-center");
		expect(rows).toHaveLength(5);
	});

	it("renders custom number of rows", () => {
		const { container } = render(<SkeletonTable rows={3} />);
		const rows = container.querySelectorAll(".flex.items-center");
		expect(rows).toHaveLength(3);
	});

	it("renders 0 rows without error", () => {
		const { container } = render(<SkeletonTable rows={0} />);
		const rows = container.querySelectorAll(".flex.items-center");
		expect(rows).toHaveLength(0);
	});
});

describe("SkeletonDetail", () => {
	it("renders without crashing", () => {
		const { container } = render(<SkeletonDetail />);
		expect(container.firstElementChild).toBeInTheDocument();
		expect(container.firstElementChild?.className).toContain("animate-pulse");
	});
});
