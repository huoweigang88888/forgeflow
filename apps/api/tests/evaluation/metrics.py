"""
ForgeFlow AI - Evaluation Metrics.

Common metrics computation for intent/decision evaluation.
Computes accuracy, precision, recall, F1, confusion matrix, etc.
"""

from collections import defaultdict
from typing import Any


def compute_accuracy(y_true: list[str], y_pred: list[str]) -> float:
    """Overall accuracy: correct / total."""
    if not y_true:
        return 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return correct / len(y_true)


def compute_per_class_metrics(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str],
) -> dict[str, dict[str, float]]:
    """Compute precision, recall, F1 for each class.

    Returns:
        {label: {precision, recall, f1, support}}
    """
    # Count TP, FP, FN per class
    tp: dict[str, int] = defaultdict(int)
    fp: dict[str, int] = defaultdict(int)
    fn: dict[str, int] = defaultdict(int)
    support: dict[str, int] = defaultdict(int)

    for true_label, pred_label in zip(y_true, y_pred):
        support[true_label] += 1
        if true_label == pred_label:
            tp[true_label] += 1
        else:
            fp[pred_label] += 1
            fn[true_label] += 1

    metrics: dict[str, dict[str, float]] = {}
    for label in labels:
        tp_count = tp[label]
        fp_count = fp[label]
        fn_count = fn[label]

        precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
        recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        metrics[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support[label],
        }

    return metrics


def compute_confusion_matrix(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str],
) -> list[list[int]]:
    """Build confusion matrix as list of rows."""
    label_to_idx = {label: i for i, label in enumerate(labels)}
    size = len(labels)
    matrix: list[list[int]] = [[0] * size for _ in range(size)]

    for true_label, pred_label in zip(y_true, y_pred):
        i = label_to_idx.get(true_label, 0)
        j = label_to_idx.get(pred_label, 0)
        matrix[i][j] += 1

    return matrix


def compute_macro_f1(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    """Macro-averaged F1 (unweighted mean of per-class F1)."""
    per_class = compute_per_class_metrics(y_true, y_pred, labels)
    f1s = [v["f1"] for v in per_class.values()]
    if not f1s:
        return 0.0
    return sum(f1s) / len(f1s)


def compute_weighted_f1(
    y_true: list[str], y_pred: list[str], labels: list[str]
) -> float:
    """Weighted-averaged F1 (weighted by support)."""
    per_class = compute_per_class_metrics(y_true, y_pred, labels)
    total = sum(v["support"] for v in per_class.values())
    if total == 0:
        return 0.0
    weighted = sum(v["f1"] * v["support"] for v in per_class.values())
    return weighted / total


def format_confusion_matrix_html(
    matrix: list[list[int]], labels: list[str]
) -> str:
    """Render confusion matrix as a simple HTML table (for reports)."""
    rows = ["<table><tr><th></th>" + "".join(f"<th>{l}</th>" for l in labels) + "</tr>"]
    for i, label in enumerate(labels):
        cells = "".join(
            f'<td style="color:{ "green" if i==j else "red" }">{matrix[i][j]}</td>'
            for j in range(len(labels))
        )
        rows.append(f"<tr><th>{label}</th>{cells}</tr>")
    rows.append("</table>")
    return "\n".join(rows)


def compare_scores(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Compare two metric dicts and return deltas."""
    deltas: dict[str, Any] = {}
    for key in baseline:
        if key in candidate and isinstance(baseline[key], (int, float)):
            deltas[key] = round(candidate[key] - baseline[key], 4)
    return deltas
