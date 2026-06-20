"""
ForgeFlow AI - Intent Evaluator.

Evaluates intent classification accuracy against a labeled test set.

From PRD Section 15.2: Intent Recognition Evaluation.
Target: Overall Accuracy >= 92%, Per-class F1 >= 0.85.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forgeflow.agent.nodes.intent import detect_intent_node
from forgeflow.agent.state import AgentState
from tests.evaluation.metrics import (
    compute_accuracy,
    compute_confusion_matrix,
    compute_macro_f1,
    compute_per_class_metrics,
)

INTENT_LABELS = [
    "shipping_delay",
    "refund_request",
    "wrong_item",
    "damaged_item",
    "exchange_request",
    "other",
]


@dataclass
class IntentTestCase:
    """A single annotated intent test case."""

    id: str
    issue_text: str
    order_id: str | None
    true_intent: str
    true_urgency: str | None = None
    true_sentiment: str | None = None
    source: str = "synthetic"  # "real" | "synthetic"
    difficulty: str = "medium"  # "easy" | "medium" | "hard"
    annotator: str | None = None


@dataclass
class IntentPrediction:
    """A single prediction from the intent node."""

    test_case_id: str
    predicted_intent: str
    confidence: float
    predicted_urgency: str | None
    predicted_sentiment: str | None
    latency_ms: float


@dataclass
class IntentEvalReport:
    """Complete intent evaluation report."""

    overall_accuracy: float
    macro_f1: float
    per_class_metrics: dict[str, dict[str, float]]
    confusion_matrix: list[list[int]]
    class_labels: list[str]
    error_analysis: list[dict[str, Any]]
    difficulty_breakdown: dict[str, float]
    total_samples: int
    total_time_ms: float
    avg_latency_ms: float


class IntentEvaluator:
    """Evaluate intent detection against an annotated test set.

    Usage:
        evaluator = IntentEvaluator(test_cases=load_intent_cases())
        report = await evaluator.evaluate()
        print(f"Accuracy: {report.overall_accuracy:.2%}")
    """

    def __init__(
        self,
        test_cases: list[IntentTestCase],
        node_fn: Any = None,
    ):
        self.test_cases = test_cases
        self._node_fn = node_fn or detect_intent_node

    async def evaluate(self) -> IntentEvalReport:
        """Run all test cases through the intent node and compute metrics."""
        predictions: list[IntentPrediction] = []
        total_start = time.perf_counter()

        for case in self.test_cases:
            pred = await self._run_single(case)
            predictions.append(pred)

        total_time_ms = (time.perf_counter() - total_start) * 1000
        return self._compute_report(predictions, total_time_ms)

    async def _run_single(self, case: IntentTestCase) -> IntentPrediction:
        """Run one test case through the intent detection node."""
        state: AgentState = {
            "ticket_id": f"eval_{case.id}",
            "platform": "mock",
            "issue_text": case.issue_text,
            "order_id": case.order_id,
            "current_step": "detect_intent",
        }

        start = time.perf_counter()
        result = await self._node_fn(state)
        latency_ms = (time.perf_counter() - start) * 1000

        return IntentPrediction(
            test_case_id=case.id,
            predicted_intent=result.get("intent", "other"),
            confidence=result.get("confidence", 0.0),
            predicted_urgency=result.get("urgency"),
            predicted_sentiment=result.get("sentiment"),
            latency_ms=latency_ms,
        )

    def _compute_report(
        self,
        predictions: list[IntentPrediction],
        total_time_ms: float,
    ) -> IntentEvalReport:
        """Aggregate predictions into an evaluation report."""
        y_true = [c.true_intent for c in self.test_cases]
        y_pred = [p.predicted_intent for p in predictions]

        accuracy = compute_accuracy(y_true, y_pred)
        macro_f1 = compute_macro_f1(y_true, y_pred, INTENT_LABELS)
        per_class = compute_per_class_metrics(y_true, y_pred, INTENT_LABELS)
        cm = compute_confusion_matrix(y_true, y_pred, INTENT_LABELS)

        # Error analysis: find misclassified samples
        errors: list[dict[str, Any]] = []
        for case, pred in zip(self.test_cases, predictions):
            if case.true_intent != pred.predicted_intent:
                errors.append({
                    "test_case_id": case.id,
                    "issue_text": case.issue_text[:200],
                    "true_intent": case.true_intent,
                    "predicted_intent": pred.predicted_intent,
                    "confidence": pred.confidence,
                    "difficulty": case.difficulty,
                })

        # Difficulty breakdown
        difficulty_breakdown: dict[str, list[tuple[int, int]]] = {"easy": [], "medium": [], "hard": []}
        for case, pred in zip(self.test_cases, predictions):
            diff = case.difficulty or "medium"
            if diff not in difficulty_breakdown:
                diff = "medium"
            correct = 1 if case.true_intent == pred.predicted_intent else 0
            difficulty_breakdown[diff].append(correct)

        difficulty_acc: dict[str, float] = {}
        for diff, results in difficulty_breakdown.items():
            if results:
                difficulty_acc[diff] = round(sum(results) / len(results), 4)

        avg_latency = total_time_ms / len(self.test_cases) if self.test_cases else 0

        return IntentEvalReport(
            overall_accuracy=round(accuracy, 4),
            macro_f1=round(macro_f1, 4),
            per_class_metrics=per_class,
            confusion_matrix=cm,
            class_labels=INTENT_LABELS,
            error_analysis=errors[:20],  # Top 20 errors
            difficulty_breakdown=difficulty_acc,
            total_samples=len(self.test_cases),
            total_time_ms=round(total_time_ms, 1),
            avg_latency_ms=round(avg_latency, 2),
        )


# =============================================================================
# Utility: Load intent test data from JSON
# =============================================================================


def load_intent_cases(path: Path | str | None = None) -> list[IntentTestCase]:
    """Load annotated intent test cases from a JSON file.

    If no path is given, looks for ``tests/evaluation/data/intent_test_set.json``.
    """
    if path is None:
        path = Path(__file__).parent / "data" / "intent_test_set.json"

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases: list[IntentTestCase] = []
    for item in data:
        cases.append(IntentTestCase(
            id=item["id"],
            issue_text=item["issue_text"],
            order_id=item.get("order_id"),
            true_intent=item["true_intent"],
            true_urgency=item.get("true_urgency"),
            true_sentiment=item.get("true_sentiment"),
            source=item.get("source", "synthetic"),
            difficulty=item.get("difficulty", "medium"),
            annotator=item.get("annotator"),
        ))
    return cases
