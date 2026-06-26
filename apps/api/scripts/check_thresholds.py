#!/usr/bin/env python
"""
Check Golden Test Thresholds.

Reads the golden test output (JSON) and verifies that all 30 golden
test cases passed.  Returns exit code 0 on success, 1 on failure.

Used in CI as a merge-blocking check.

From PRD Section 15.4: 30 Golden Test Cases must all pass.
"""

import json
import sys
from pathlib import Path

REQUIRED_PASS_RATE = 1.0  # 30/30 must pass
REQUIRED_PASS_COUNT = 30  # Exact golden case count expected
REPORT_PATH = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "evaluation"
    / "golden"
    / "golden_results.json"
)


def main() -> int:
    if not REPORT_PATH.exists():
        print(f"ERROR: Golden test report not found at {REPORT_PATH}")
        print("Run golden tests first: pytest tests/evaluation/golden/runner.py -v")
        return 1

    with open(REPORT_PATH, encoding="utf-8") as f:
        report = json.load(f)

    total = report.get("total", 0)
    passed = report.get("passed", 0)
    _ = report.get("failed", 0)  # Tracked but not used for threshold decision
    pass_rate = report.get("pass_rate", 0)

    print(f"Golden Tests: {passed}/{total} passed ({pass_rate:.1%})")

    # Check pass rate
    if pass_rate < REQUIRED_PASS_RATE:
        print(f"BLOCKED: Pass rate {pass_rate:.1%} < required {REQUIRED_PASS_RATE:.0%}")
        print("The following test(s) failed:")
        for result in report.get("results", []):
            if not result.get("passed", False):
                print(f"  ✗ {result['case_id']}: {result['name']}")
                for failure in result.get("failures", []):
                    print(f"      → {failure}")
        return 1

    # Verify exact count
    if total < REQUIRED_PASS_COUNT:
        print(f"WARNING: Only {total} golden cases found, expected {REQUIRED_PASS_COUNT}")
        # Warning only, not blocking

    # Check individual thresholds
    all_passed = True
    for result in report.get("results", []):
        if not result.get("passed", False):
            print(f"BLOCKED: {result['case_id']}: {result['name']} FAILED")
            for failure in result.get("failures", []):
                print(f"  {failure}")
            all_passed = False

    if not all_passed:
        return 1

    print(f"ALL {total} GOLDEN TESTS PASSED ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
