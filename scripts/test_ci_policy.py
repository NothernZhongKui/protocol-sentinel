#!/usr/bin/env python3
"""Deterministic policy matrix and fail-closed controls."""

from ci_policy import (
    MATRIX,
    VERSION,
    aggregate,
    verdict_decision,
)


def check(actual, expected, label):
    assert actual == expected, (
        f"{label}: expected {expected!r}, got {actual!r}"
    )
    print(f"PASS | {label}")


def run():
    check(VERSION, "1", "Policy version")

    check(
        len(MATRIX),
        6,
        "Six supported comparison verdicts",
    )

    for verdict, (decision, reason) in MATRIX.items():
        actual = verdict_decision(verdict)

        check(
            actual,
            {"decision": decision, "reason": reason},
            f"{verdict} -> {decision}",
        )

    for invalid in (
        None, "", "PASS", "MATCH", "GREEN", 1, True, {}
    ):
        check(
            verdict_decision(invalid)["decision"],
            "BLOCK",
            f"Unknown verdict {invalid!r}",
        )

    def scenario(name, verdict):
        return {"id": name, "verdict": verdict}

    safe = scenario(
        "treasury_safe", "STILL_SATISFIED"
    )

    unsafe = scenario(
        "treasury_unsafe", "CHANGED_TO_VIOLATION"
    )

    review = scenario(
        "treasury_review", "CHANGED_TO_SATISFIED"
    )

    check(
        aggregate(["treasury_safe"], [safe])["decision"],
        "PASS",
        "Safe comparison permits PASS",
    )

    check(
        aggregate(["treasury_unsafe"], [unsafe])["decision"],
        "BLOCK",
        "New violation BLOCK",
    )

    check(
        aggregate(
            ["treasury_safe", "treasury_unsafe"],
            [safe, unsafe],
        )["decision"],
        "BLOCK",
        "BLOCK dominates PASS",
    )

    check(
        aggregate(
            ["treasury_safe", "treasury_review"],
            [safe, review],
        )["decision"],
        "REVIEW",
        "REVIEW dominates PASS",
    )

    check(
        aggregate([], [])["reason"],
        "EMPTY_OR_INVALID_INVENTORY",
        "Empty inventory rejected",
    )

    check(
        aggregate(["treasury_safe"], [])["reason"],
        "MISSING_REQUIRED_SCENARIO",
        "Missing required scenario rejected",
    )

    check(
        aggregate(
            ["treasury_safe", "treasury_safe"],
            [safe],
        )["reason"],
        "DUPLICATE_REQUIRED_SCENARIO",
        "Duplicate inventory rejected",
    )

    check(
        aggregate(
            ["treasury_safe"],
            [safe, safe],
        )["reason"],
        "DUPLICATE_COMPARISON",
        "Duplicate comparison rejected",
    )

    check(
        aggregate(
            ["treasury_safe"],
            [unsafe],
        )["reason"],
        "UNEXPECTED_SCENARIO",
        "Unexpected scenario rejected",
    )

    check(
        aggregate(
            ["treasury_safe"],
            [scenario("treasury_safe", "FORGED_PASS")],
        )["decision"],
        "BLOCK",
        "Forged verdict rejected",
    )

    check(
        aggregate(
            ["treasury_safe"],
            [{
                **safe,
                "verification": "PASS",
            }],
        )["reason"],
        "INVALID_COMPARISON_ENTRY",
        "Untrusted verification claim rejected",
    )

    check(
        aggregate(
            ["treasury_safe"],
            [{
                **safe,
                "ci_decision": "PASS",
            }],
        )["reason"],
        "INVALID_COMPARISON_ENTRY",
        "Untrusted precomputed decision rejected",
    )

    print()
    print("=== POLICY MATRIX AND NEGATIVE CONTROLS PASS ===")


if __name__ == "__main__":
    run()
