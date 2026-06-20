"""
ForgeFlow AI - Golden Test Runner.

Runs YAML-based golden test cases through the full agent pipeline and
validates expected outputs.  Integrated into CI as a merge-blocking check.

From PRD Section 15.4: End-to-End Regression Tests (Golden Test Cases).
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from forgeflow.agent.service import AgentService


@dataclass
class GoldenTestCase:
    """A single golden test case loaded from YAML."""

    id: str
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    input: dict[str, Any] = field(default_factory=dict)
    mock_overrides: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)


@dataclass
class GoldenTestResult:
    """Result of running a single golden test case."""

    case_id: str
    name: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    actual: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class GoldenTestReport:
    """Aggregate golden test report."""

    total: int
    passed: int
    failed: int
    pass_rate: float
    results: list[GoldenTestResult]
    total_time_ms: float


class GoldenTestRunner:
    """Runs golden YAML test cases through the full agent pipeline.

    Each golden case defines:
    - Input: ticket data (issue_text, order_id, customer_email, etc.)
    - Mock overrides: Specific mock provider behavior for this case
    - Expected: What the agent should output (action, approval, amount, status)

    Usage:
        runner = GoldenTestRunner(Path("tests/evaluation/golden/cases"))
        report = await runner.run_all()
        assert report.failed == 0, f"{report.failed} golden tests failed"
    """

    def __init__(self, cases_dir: Path):
        self.cases_dir = Path(cases_dir)

    async def run_all(self) -> GoldenTestReport:
        """Load, run, and validate all golden test cases."""
        results: list[GoldenTestResult] = []
        total_start = time.perf_counter()

        # Load all YAML case files
        case_files = sorted(self.cases_dir.glob("*.yaml"))
        for case_file in case_files:
            cases = self._load_cases(case_file)
            for case in cases:
                result = await self.run_single(case)
                results.append(result)

        total_time_ms = (time.perf_counter() - total_start) * 1000

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed

        return GoldenTestReport(
            total=len(results),
            passed=passed,
            failed=failed,
            pass_rate=round(passed / len(results), 4) if results else 0.0,
            results=results,
            total_time_ms=round(total_time_ms, 1),
        )

    def _load_cases(self, file_path: Path) -> list[GoldenTestCase]:
        """Load golden test cases from a YAML file.

        Supports multi-document YAML (separated by ``---``).
        """
        with open(file_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))

        cases: list[GoldenTestCase] = []
        for doc in docs:
            if doc is None:
                continue
            if isinstance(doc, dict):
                cases.append(GoldenTestCase(
                    id=doc.get("id", ""),
                    name=doc.get("name", ""),
                    description=doc.get("description", ""),
                    tags=doc.get("tags", []),
                    input=doc.get("input", {}),
                    mock_overrides=doc.get("mock_overrides", {}),
                    expected=doc.get("expected", {}),
                ))
            elif isinstance(doc, list):
                for item in doc:
                    cases.append(GoldenTestCase(
                        id=item.get("id", ""),
                        name=item.get("name", ""),
                        description=item.get("description", ""),
                        tags=item.get("tags", []),
                        input=item.get("input", {}),
                        mock_overrides=item.get("mock_overrides", {}),
                        expected=item.get("expected", {}),
                    ))

        return cases

    async def run_single(self, case: GoldenTestCase) -> GoldenTestResult:
        """Run a single golden test case and validate results."""
        start = time.perf_counter()
        failures: list[str] = []
        warnings: list[str] = []
        actual: dict[str, Any] = {}

        try:
            service = AgentService(redis_client=None)

            result = await service.run(
                ticket_id=case.id,
                platform=case.input.get("platform", "mock"),
                shopify_domain=case.input.get("shopify_domain", "test.myshopify.com"),
                customer_email=case.input.get("customer_email", "test@example.com"),
                issue_text=case.input.get("issue_text", ""),
                order_id=case.input.get("order_id"),
                customer_name=case.input.get("customer_name"),
                mock_overrides=case.mock_overrides,
            )
            actual = result

        except Exception as e:
            failures.append(f"Pipeline exception: {e}")
            duration_ms = (time.perf_counter() - start) * 1000
            return GoldenTestResult(
                case_id=case.id,
                name=case.name,
                passed=False,
                failures=failures,
                actual={"error": str(e)},
                duration_ms=duration_ms,
            )

        # Validate against expected
        expected = case.expected
        duration_ms = (time.perf_counter() - start) * 1000

        # 1. Check recommended_action (BLOCKING)
        if "recommended_action" in expected:
            exp_action = expected["recommended_action"]
            actual_action = result.get("recommended_action")
            if actual_action != exp_action:
                failures.append(
                    f"recommended_action mismatch: "
                    f"expected={exp_action}, actual={actual_action}"
                )

        # 2. Check requires_approval (BLOCKING)
        if "requires_approval" in expected:
            exp_approval = expected["requires_approval"]
            actual_approval = result.get("requires_approval", False)
            if actual_approval != exp_approval:
                failures.append(
                    f"requires_approval mismatch: "
                    f"expected={exp_approval}, actual={actual_approval}"
                )

        # 3. Check refund_amount (WARNING only, per PRD)
        if "refund_amount_range" in expected:
            lo, hi = expected["refund_amount_range"]
            actual_amount = result.get("refund_amount", 0.0) or 0.0
            if not (lo <= actual_amount <= hi):
                warnings.append(
                    f"refund_amount out of range [{lo}, {hi}]: "
                    f"actual={actual_amount}"
                )

        # 4. Check intent (if expected)
        if "intent" in expected:
            exp_intent = expected["intent"]
            actual_intent = result.get("intent")
            if actual_intent != exp_intent:
                failures.append(
                    f"intent mismatch: expected={exp_intent}, actual={actual_intent}"
                )

        # 5. Check status
        if "status" in expected:
            exp_status = expected["status"]
            actual_status = result.get("status")
            if actual_status != exp_status:
                failures.append(
                    f"status mismatch: expected={exp_status}, actual={actual_status}"
                )

        # 6. Check confidence minimum
        if "confidence_min" in expected:
            actual_conf = result.get("confidence", 0.0) or 0.0
            if actual_conf < expected["confidence_min"]:
                warnings.append(
                    f"confidence below minimum: "
                    f"expected >= {expected['confidence_min']}, actual={actual_conf}"
                )

        passed = len(failures) == 0

        return GoldenTestResult(
            case_id=case.id,
            name=case.name,
            passed=passed,
            failures=failures,
            warnings=warnings,
            actual=actual,
            duration_ms=duration_ms,
        )


# =============================================================================
# Helpers
# =============================================================================


def dump_report_json(report: GoldenTestReport, path: Path) -> None:
    """Write the golden test report as JSON (for CI threshold checks)."""
    data = {
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "pass_rate": report.pass_rate,
        "total_time_ms": report.total_time_ms,
        "results": [
            {
                "case_id": r.case_id,
                "name": r.name,
                "passed": r.passed,
                "failures": r.failures,
                "warnings": r.warnings,
                "duration_ms": r.duration_ms,
            }
            for r in report.results
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
