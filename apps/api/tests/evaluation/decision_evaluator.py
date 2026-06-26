"""
ForgeFlow AI - Decision Evaluator.

Evaluates decision accuracy against a labeled test set of 100 cases
with orthogonal coverage (intent x fulfillment x amount).

From PRD Section 15.3: Decision Accuracy Evaluation.
Targets:
  - Action accuracy >= 90% (weight 40%)
  - Amount accuracy >= 95% (weight 20%)
  - Approval recall >= 95% (weight 30%)  — SAFETY CRITICAL
  - Approval precision >= 90% (weight 10%)
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from forgeflow.agent.nodes.decision import make_decision_node
from forgeflow.agent.state import AgentState


@dataclass
class DecisionTestCase:
    """A single annotated decision test case."""

    id: str
    input_state: dict[str, Any]  # Partial AgentState up to decision node
    expected_action: str
    expected_requires_approval: bool
    expected_refund_amount: float | None = None
    amount_tolerance: float = 0.05  # 5% tolerance
    explanation_contains: list[str] = field(default_factory=list)


@dataclass
class DecisionEvalReport:
    """Complete decision evaluation report."""

    action_accuracy: float
    amount_accuracy: float
    approval_recall: float
    approval_precision: float
    weighted_score: float  # Weighted composite score
    total_samples: int
    action_errors: list[dict[str, Any]]
    amount_errors: list[dict[str, Any]]
    approval_errors: list[dict[str, Any]]  # Cases where approval was wrong
    total_time_ms: float
    avg_latency_ms: float


class DecisionEvaluator:
    """Evaluate decision-making against an annotated test set.

    Usage:
        evaluator = DecisionEvaluator(test_cases=load_decision_cases())
        report = await evaluator.evaluate()
        print(f"Weighted Score: {report.weighted_score:.2%}")
    """

    # Weights per PRD Section 15.3
    WEIGHT_ACTION = 0.40
    WEIGHT_AMOUNT = 0.20
    WEIGHT_APPROVAL_RECALL = 0.30  # Safety-critical
    WEIGHT_APPROVAL_PRECISION = 0.10

    ACTIONS: ClassVar[list[str]] = [
        "auto_refund",
        "auto_exchange",
        "investigate",
        "escalate_to_human",
        "send_notification",
    ]

    def __init__(
        self,
        test_cases: list[DecisionTestCase],
        node_fn: Any = None,
    ):
        self.test_cases = test_cases
        self._node_fn = node_fn or make_decision_node

    async def evaluate(self) -> DecisionEvalReport:
        """Run all test cases and compute metrics."""
        results: list[dict[str, Any]] = []
        total_start = time.perf_counter()

        for case in self.test_cases:
            result = await self._run_single(case)
            results.append(result)

        total_time_ms = (time.perf_counter() - total_start) * 1000
        return self._compute_report(results, total_time_ms)

    async def _run_single(self, case: DecisionTestCase) -> dict[str, Any]:
        """Run one decision test case."""
        state: AgentState = {
            "ticket_id": f"decision_eval_{case.id}",
            "platform": "mock",
            "llm_call_count": 0,
            **case.input_state,
            "current_step": "make_decision",
        }

        start = time.perf_counter()
        result = await self._node_fn(state)
        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "test_case_id": case.id,
            "predicted_action": result.get("recommended_action"),
            "predicted_requires_approval": result.get("requires_approval", False),
            "predicted_refund_amount": result.get("refund_amount", 0.0),
            "expected_action": case.expected_action,
            "expected_requires_approval": case.expected_requires_approval,
            "expected_refund_amount": case.expected_refund_amount,
            "amount_tolerance": case.amount_tolerance,
            "latency_ms": latency_ms,
        }

    def _compute_report(
        self, results: list[dict[str, Any]], total_time_ms: float
    ) -> DecisionEvalReport:
        """Aggregate results into an evaluation report."""
        total = len(results)
        if total == 0:
            return DecisionEvalReport(0, 0, 0, 0, 0, 0, [], [], [], 0, 0)

        # --- Action accuracy ---
        action_correct = 0
        action_errors: list[dict[str, Any]] = []
        for r in results:
            if r["predicted_action"] == r["expected_action"]:
                action_correct += 1
            else:
                action_errors.append(
                    {
                        "test_case_id": r["test_case_id"],
                        "expected": r["expected_action"],
                        "predicted": r["predicted_action"],
                    }
                )
        action_acc = action_correct / total

        # --- Amount accuracy ---
        amount_correct = 0
        amount_errors: list[dict[str, Any]] = []
        for r in results:
            expected_amt = r["expected_refund_amount"]
            if expected_amt is None:
                amount_correct += 1
                continue
            predicted_amt = r["predicted_refund_amount"] or 0.0
            if expected_amt == 0:
                if predicted_amt == 0:
                    amount_correct += 1
                else:
                    amount_errors.append(
                        {
                            "test_case_id": r["test_case_id"],
                            "expected": expected_amt,
                            "predicted": predicted_amt,
                            "error_pct": 1.0,
                        }
                    )
            else:
                error_pct = abs(predicted_amt - expected_amt) / expected_amt
                if error_pct <= r["amount_tolerance"]:
                    amount_correct += 1
                else:
                    amount_errors.append(
                        {
                            "test_case_id": r["test_case_id"],
                            "expected": expected_amt,
                            "predicted": predicted_amt,
                            "error_pct": round(error_pct, 4),
                        }
                    )
        amount_acc = amount_correct / total

        # --- Approval recall (safety-critical) ---
        # "Of cases that NEED approval, what fraction were flagged?"
        needs_approval = [r for r in results if r["expected_requires_approval"]]
        approval_recall = 1.0
        if needs_approval:
            approval_correct = sum(1 for r in needs_approval if r["predicted_requires_approval"])
            approval_recall = approval_correct / len(needs_approval)

        # --- Approval precision ---
        # "Of flagged cases, what fraction actually needed approval?"
        flagged = [r for r in results if r["predicted_requires_approval"]]
        approval_precision = 1.0
        if flagged:
            flagged_correct = sum(1 for r in flagged if r["expected_requires_approval"])
            approval_precision = flagged_correct / len(flagged)

        # Approval errors (false positives + false negatives)
        approval_errors: list[dict[str, Any]] = []
        for r in results:
            if r["predicted_requires_approval"] != r["expected_requires_approval"]:
                approval_errors.append(
                    {
                        "test_case_id": r["test_case_id"],
                        "expected": r["expected_requires_approval"],
                        "predicted": r["predicted_requires_approval"],
                        "type": "false_negative"
                        if r["expected_requires_approval"]
                        else "false_positive",
                    }
                )

        # --- Weighted composite score ---
        weighted = (
            self.WEIGHT_ACTION * action_acc
            + self.WEIGHT_AMOUNT * amount_acc
            + self.WEIGHT_APPROVAL_RECALL * approval_recall
            + self.WEIGHT_APPROVAL_PRECISION * approval_precision
        )

        avg_latency = total_time_ms / total

        return DecisionEvalReport(
            action_accuracy=round(action_acc, 4),
            amount_accuracy=round(amount_acc, 4),
            approval_recall=round(approval_recall, 4),
            approval_precision=round(approval_precision, 4),
            weighted_score=round(weighted, 4),
            total_samples=total,
            action_errors=action_errors[:10],
            amount_errors=amount_errors[:10],
            approval_errors=approval_errors,
            total_time_ms=round(total_time_ms, 1),
            avg_latency_ms=round(avg_latency, 2),
        )


# =============================================================================
# Utility: Load decision test data from JSON
# =============================================================================


def load_decision_cases(path: Path | str | None = None) -> list[DecisionTestCase]:
    """Load annotated decision test cases from a JSON file."""
    if path is None:
        path = Path(__file__).parent / "data" / "decision_test_set.json"

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    cases: list[DecisionTestCase] = []
    for item in data:
        cases.append(
            DecisionTestCase(
                id=item["id"],
                input_state=item["input_state"],
                expected_action=item["expected_action"],
                expected_requires_approval=item["expected_requires_approval"],
                expected_refund_amount=item.get("expected_refund_amount"),
                amount_tolerance=item.get("amount_tolerance", 0.05),
                explanation_contains=item.get("explanation_contains", []),
            )
        )
    return cases
