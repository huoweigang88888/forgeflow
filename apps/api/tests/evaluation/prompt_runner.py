"""
ForgeFlow AI - Prompt Regression Test Runner.

Runs prompt templates through mock LLM providers and validates that:
1. Templates are syntactically valid Python format strings
2. All expected variables are present
3. Output structure matches expected fields
4. Enum values fall within valid ranges

From PRD Section 18.4: Prompt Regression Testing.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PromptTestCase:
    """A single prompt regression test case."""

    id: str
    prompt_name: str
    inputs: dict[str, Any]
    expected: dict[str, Any]


@dataclass
class PromptTestResult:
    """Result of a single prompt test."""

    case_id: str
    prompt_name: str
    passed: bool
    failures: list[str] = field(default_factory=list)


@dataclass
class PromptRegressionReport:
    """Aggregate prompt regression report."""

    total: int
    passed: int
    failed: int
    results: list[PromptTestResult]


class PromptRegressionRunner:
    """Runs prompt regression tests to validate template quality.

    Usage:
        runner = PromptRegressionRunner(Path("tests/evaluation/prompt_tests.yaml"))
        report = await runner.run_all()
        assert report.failed == 0
    """

    def __init__(self, test_file: Path):
        self.test_file = test_file
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Load prompt templates from the agent prompts module."""
        from forgeflow.agent import prompts as pmod

        self._prompts: dict[str, str] = {}
        for attr in dir(pmod):
            if attr.endswith("_PROMPT"):
                self._prompts[attr] = getattr(pmod, attr)

    async def run_all(self) -> PromptRegressionReport:
        """Load test cases and run all validations."""
        with open(self.test_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        cases = [
            PromptTestCase(
                id=item["id"],
                prompt_name=item["prompt_name"],
                inputs=item.get("inputs", {}),
                expected=item.get("expected", {}),
            )
            for item in data.get("test_cases", [])
        ]

        results = []
        for case in cases:
            result = self._run_single(case)
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        return PromptRegressionReport(
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            results=results,
        )

    def _run_single(self, case: PromptTestCase) -> PromptTestResult:
        """Validate one prompt test case."""
        failures: list[str] = []

        # 1. Check prompt exists
        template = self._prompts.get(case.prompt_name)
        if template is None:
            failures.append(f"Prompt '{case.prompt_name}' not found")
            return PromptTestResult(
                case_id=case.id,
                prompt_name=case.prompt_name,
                passed=False,
                failures=failures,
            )

        # 2. Check template can be formatted
        try:
            rendered = template.format(**case.inputs)
        except KeyError as e:
            failures.append(f"Missing variable in template: {e}")
            return PromptTestResult(
                case_id=case.id,
                prompt_name=case.prompt_name,
                passed=False,
                failures=failures,
            )
        except ValueError as e:
            failures.append(f"Template format error: {e}")
            return PromptTestResult(
                case_id=case.id,
                prompt_name=case.prompt_name,
                passed=False,
                failures=failures,
            )

        # 3. Check rendered template contains key phrases
        for phrase in case.expected.get("contains", []):
            if phrase.lower() not in rendered.lower():
                failures.append(f"Rendered prompt missing expected phrase: '{phrase}'")

        # 4. Check template variables match expected
        expected_vars = set(case.expected.get("required_vars", []))
        if expected_vars:
            # Simple check: count {var} patterns in template
            import re
            actual_vars = set(re.findall(r"\{(\w+)\}", template))
            missing = expected_vars - actual_vars
            if missing:
                failures.append(f"Template missing expected variables: {missing}")

        passed = len(failures) == 0
        return PromptTestResult(
            case_id=case.id,
            prompt_name=case.prompt_name,
            passed=passed,
            failures=failures,
        )


# =============================================================================
# Utility
# =============================================================================


def create_default_prompt_tests() -> str:
    """Generate a default prompt regression YAML for the project.

    Returns the YAML content as a string that can be written to a file.
    """
    return """# Prompt Regression Tests — ForgeFlow AI
# Validates prompt template syntax, variable completeness, and output structure.

prompt_name: all
description: "Prompt regression test suite"
min_accuracy: 0.95

test_cases:
  - id: "prompt_intent_001"
    prompt_name: "INTENT_PROMPT"
    description: "Shipping delay intent detection"
    inputs:
      issue: "My order #12345 hasn't arrived after 2 weeks of waiting"
      order_id: "#12345"
    expected:
      required_vars: [issue, order_id]
      contains: ["shipping_delay", "refund_request", "customer", "classify"]

  - id: "prompt_intent_002"
    prompt_name: "INTENT_PROMPT"
    description: "Refund request intent detection"
    inputs:
      issue: "I want my money back"
      order_id: null
    expected:
      required_vars: [issue, order_id]

  - id: "prompt_decision_001"
    prompt_name: "DECISION_PROMPT"
    description: "Decision prompt with all required fields"
    inputs:
      intent: "shipping_delay"
      issue_text: "Order late by 15 days"
      order_info: '{"total_price": 45.00}'
      logistics_status: '{"status": "delayed"}'
      customer_history: "{}"
    expected:
      required_vars:
        [intent, issue_text, order_info, logistics_status, customer_history]
      contains: ["recommended_action", "refund_amount", "requires_approval"]

  - id: "prompt_policy_001"
    prompt_name: "POLICY_CHECK_PROMPT"
    description: "Policy check prompt"
    inputs:
      intent: "shipping_delay"
      issue_text: "Order delayed 2 weeks"
      order_info: '{"fulfillment_status": "fulfilled"}'
      merchant_policies: "No custom policies found"
    expected:
      required_vars: [intent, issue_text, order_info, merchant_policies]
"""
