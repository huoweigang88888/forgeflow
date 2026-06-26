"""
ForgeFlow AI - Prompt Regression Test Runner.

Runs YAML-based regression tests against prompt templates to ensure
changes don't degrade accuracy. Integrated into CI pipeline.

From PRD Section 18.4: Prompt Regression Tests.

Usage:
    pytest tests/evaluation/prompt_runner.py -v
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from forgeflow.llm.base import LLMProvider
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="evaluation.prompts")


@dataclass
class PromptTestCase:
    """A single prompt regression test case."""

    id: str
    input: dict[str, str]
    expected: dict[str, Any]
    description: str = ""


@dataclass
class PromptTestResult:
    """Result of running a single prompt test case."""

    case_id: str
    passed: bool
    actual: dict[str, Any]
    failures: list[str] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class PromptTestReport:
    """Aggregate prompt regression test report."""

    prompt_name: str
    version: str
    total: int
    passed: int
    failed: int
    accuracy: float
    avg_latency_ms: float
    results: list[PromptTestResult]


class PromptRegressionRunner:
    """Run regression tests against a prompt template.

    Each test case defines:
    - input: Variables to render into the prompt template
    - expected: What the LLM should output (field-level assertions)

    Usage:
        runner = PromptRegressionRunner(llm_provider)
        report = await runner.run(
            prompt_name="intent_detection",
            template=INTENT_PROMPT,
            test_cases=loaded_cases,
        )
        assert report.accuracy >= 0.90, "Accuracy below threshold!"
    """

    def __init__(self, llm_provider: LLMProvider, min_accuracy: float = 0.90):
        self.llm = llm_provider
        self.min_accuracy = min_accuracy

    async def run(
        self,
        prompt_name: str,
        version: str,
        template: str,
        test_cases: list[PromptTestCase],
    ) -> PromptTestReport:
        """Run all test cases against a prompt template."""
        results: list[PromptTestResult] = []

        for case in test_cases:
            result = await self._run_single(template, case)
            results.append(result)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        accuracy = round(passed / total, 4) if total > 0 else 0.0
        avg_latency = sum(r.duration_ms for r in results) / total if total > 0 else 0.0

        report = PromptTestReport(
            prompt_name=prompt_name,
            version=version,
            total=total,
            passed=passed,
            failed=failed,
            accuracy=accuracy,
            avg_latency_ms=round(avg_latency, 1),
            results=results,
        )

        # Log failures
        if failed > 0:
            logger.warning(
                "prompt_regression_failures",
                prompt_name=prompt_name,
                version=version,
                failed=failed,
                total=total,
                accuracy=accuracy,
            )

        return report

    async def _run_single(self, template: str, case: PromptTestCase) -> PromptTestResult:
        """Run a single test case."""
        start = time.perf_counter()
        failures: list[str] = []
        actual: dict[str, Any] = {}

        try:
            # Render template with input variables
            rendered = template.format(**case.input)

            # Call LLM
            raw_response = await self.llm.complete(rendered)
            actual = json.loads(raw_response)

            # Validate against expected
            for field, expected_value in case.expected.items():
                if field.endswith("_min"):
                    # Numeric minimum check: confidence_min -> confidence >= value
                    actual_field = field[:-4]  # Strip '_min'
                    actual_val = actual.get(actual_field, 0)
                    if isinstance(actual_val, int | float) and actual_val < expected_value:
                        failures.append(f"{actual_field}={actual_val} < min {expected_value}")
                elif field.endswith("_contains"):
                    # String contains check
                    actual_field = field[:-9]
                    actual_val = str(actual.get(actual_field, ""))
                    if expected_value not in actual_val:
                        failures.append(f"{actual_field} does not contain '{expected_value}'")
                elif field in actual:
                    if actual[field] != expected_value:
                        failures.append(
                            f"{field}: expected={expected_value}, actual={actual[field]}"
                        )
                else:
                    failures.append(f"Missing field: {field}")

        except json.JSONDecodeError as e:
            failures.append(f"JSON parse error: {e}")
        except Exception as e:
            failures.append(f"Unexpected error: {e}")

        duration_ms = (time.perf_counter() - start) * 1000

        return PromptTestResult(
            case_id=case.id,
            passed=len(failures) == 0,
            actual=actual,
            failures=failures,
            duration_ms=round(duration_ms, 1),
        )

    @staticmethod
    def load_cases(yaml_path: Path) -> list[PromptTestCase]:
        """Load test cases from a YAML file."""
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        cases: list[PromptTestCase] = []
        for item in data.get("test_cases", []):
            cases.append(
                PromptTestCase(
                    id=item["id"],
                    input=item.get("input", {}),
                    expected=item.get("expected", {}),
                    description=item.get("description", ""),
                )
            )
        return cases


def check_accuracy_threshold(report: PromptTestReport) -> bool:
    """Check if a report meets the minimum accuracy threshold.

    Returns True if the report passes, False otherwise.
    Prints a summary to stdout for CI consumption.
    """
    passed = (
        report.accuracy >= report.min_accuracy
        if hasattr(report, "min_accuracy")
        else report.accuracy >= 0.90
    )

    print(f"\n{'=' * 60}")
    print(f"Prompt: {report.prompt_name} v{report.version}")
    print(f"Accuracy: {report.accuracy:.1%} ({report.passed}/{report.total})")
    print(f"Avg Latency: {report.avg_latency_ms:.0f}ms")
    print(f"Threshold: {0.90 if not hasattr(report, 'min_accuracy') else report.min_accuracy:.0%}")
    print(f"Result: {'PASS' if passed else 'FAIL'}")

    if report.failed > 0:
        print("\nFailed cases:")
        for r in report.results:
            if not r.passed:
                print(f"  ✗ {r.case_id}: {', '.join(r.failures)}")

    print(f"{'=' * 60}\n")

    return passed
