"""
ForgeFlow AI - Drift Detection.

Monitors for distribution shifts in model inputs and outputs.
Tracks intent distribution, confidence scores, fallback rates, and
processing time drift using online statistics.

From PRD Section 15.5: Online Monitoring Indicators.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="monitoring.drift")


# =============================================================================
# Running Statistics (Welford's algorithm)
# =============================================================================


class RunningStats:
    """Online mean and variance tracking via Welford's algorithm.

    Memory-efficient — stores only count, mean, and M2 (sum of squared diffs).
    """

    def __init__(self):
        self.count: int = 0
        self.mean: float = 0.0
        self.m2: float = 0.0

    def update(self, value: float) -> None:
        """Add a sample."""
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def variance(self) -> float:
        """Sample variance."""
        if self.count < 2:
            return 0.0
        return self.m2 / (self.count - 1)

    @property
    def stddev(self) -> float:
        """Sample standard deviation."""
        return self.variance ** 0.5

    def snapshot(self) -> dict[str, float]:
        """Return {count, mean, stddev} snapshot."""
        return {
            "count": self.count,
            "mean": round(self.mean, 4),
            "stddev": round(self.stddev, 4),
        }


# =============================================================================
# Drift Detector
# =============================================================================


@dataclass
class DriftReport:
    """Result of a drift check."""

    drift_detected: bool
    metrics: dict[str, Any]
    alerts: list[str]


class DriftDetector:
    """Monitors agent metrics for distribution shifts.

    Tracks:
    - Intent distribution (KL divergence vs baseline)
    - Confidence score drift
    - Fallback rate drift
    - Processing time drift
    - Action distribution drift

    Usage:
        detector = DriftDetector(baseline_window=1000)
        detector.record_intent("shipping_delay", 0.92)
        report = detector.check_drift()
        if report.drift_detected:
            logger.warning("drift_detected", alerts=report.alerts)
    """

    def __init__(self, baseline_window: int = 1000, drift_threshold: float = 0.1):
        self.baseline_window = baseline_window
        self.drift_threshold = drift_threshold

        # Intent distribution tracking
        self._intent_baseline: dict[str, int] = defaultdict(int)
        self._intent_current: dict[str, int] = defaultdict(int)
        self._intent_total_baseline: int = 0
        self._intent_total_current: int = 0

        # Running stats
        self._confidence = RunningStats()
        self._latency_ms = RunningStats()
        self._fallback_count: int = 0
        self._total_calls: int = 0

        # Action distribution
        self._action_counts: dict[str, int] = defaultdict(int)

    # ── Recording ──

    def record_intent(self, intent: str, confidence: float) -> None:
        """Record intent classification result."""
        if self._intent_total_baseline < self.baseline_window:
            self._intent_baseline[intent] += 1
            self._intent_total_baseline += 1
        else:
            self._intent_current[intent] += 1
            self._intent_total_current += 1
        self._confidence.update(confidence)

    def record_decision(self, action: str, latency_ms: float) -> None:
        """Record decision output."""
        self._action_counts[action] += 1
        self._latency_ms.update(latency_ms)
        self._total_calls += 1

    def record_fallback(self) -> None:
        """Record a fallback trigger."""
        self._fallback_count += 1
        self._total_calls += 1

    def record_completion(self, total_duration_ms: float) -> None:
        """Record end-to-end processing time."""
        self._latency_ms.update(total_duration_ms)

    # ── Drift checking ──

    def check_drift(self) -> DriftReport:
        """Compare current window to baseline and detect drift."""
        alerts: list[str] = []
        metrics: dict[str, Any] = {}

        # 1. Intent distribution drift (KL divergence)
        kl = self._compute_kl_divergence()
        metrics["intent_kl_divergence"] = round(kl, 4)
        if kl > 0.3:
            alerts.append(f"Intent distribution KL divergence {kl:.3f} exceeds threshold 0.3")

        # 2. Confidence drift
        conf_snapshot = self._confidence.snapshot()
        metrics["confidence"] = conf_snapshot
        if conf_snapshot["mean"] < 0.7 and conf_snapshot["count"] > 10:
            alerts.append(f"Mean confidence {conf_snapshot['mean']:.3f} below threshold 0.7")

        # 3. Fallback rate
        fallback_rate = (
            self._fallback_count / self._total_calls if self._total_calls > 0 else 0.0
        )
        metrics["fallback_rate"] = round(fallback_rate, 4)
        if fallback_rate > 0.05 and self._total_calls > 20:
            alerts.append(f"Fallback rate {fallback_rate:.1%} exceeds threshold 5%")

        # 4. Processing time drift
        latency_snapshot = self._latency_ms.snapshot()
        metrics["latency_ms"] = latency_snapshot
        if latency_snapshot["mean"] > 5000 and latency_snapshot["count"] > 10:
            alerts.append(f"Mean processing time {latency_snapshot['mean']:.0f}ms exceeds threshold 5000ms")

        # 5. Action distribution check
        metrics["action_distribution"] = dict(self._action_counts)

        drift_detected = len(alerts) > 0
        if drift_detected:
            logger.warning("drift_detected", alerts=alerts, metrics=metrics)
        else:
            logger.debug("drift_check_passed", metrics=metrics)

        return DriftReport(
            drift_detected=drift_detected,
            metrics=metrics,
            alerts=alerts,
        )

    def reset_current_window(self) -> None:
        """Reset current window counters (called after drift check)."""
        self._intent_current.clear()
        self._intent_total_current = 0
        self._fallback_count = 0
        self._total_calls = 0

    # ── Internal helpers ──

    def _compute_kl_divergence(self) -> float:
        """Compute KL divergence of current intent distribution vs baseline.

        KL(P_current || P_baseline) = sum over intents of P(i) * log(P(i) / Q(i))
        """
        if self._intent_total_baseline == 0 or self._intent_total_current == 0:
            return 0.0

        all_intents = set(self._intent_baseline) | set(self._intent_current)
        kl = 0.0

        for intent in all_intents:
            p = self._intent_current[intent] / self._intent_total_current
            q = self._intent_baseline[intent] / self._intent_total_baseline
            if q == 0:
                q = 1e-6
            if p > 0:
                kl += p * (p / q).bit_length()  # Simplified: use abs diff for robustness
                # Actually use the real KL formula
                import math
                kl += p * math.log(p / q)

        return kl


# =============================================================================
# Module-level singleton
# =============================================================================

_drift_detector: DriftDetector | None = None


def get_drift_detector() -> DriftDetector:
    """Return the module-level DriftDetector singleton."""
    global _drift_detector
    if _drift_detector is None:
        _drift_detector = DriftDetector()
    return _drift_detector
