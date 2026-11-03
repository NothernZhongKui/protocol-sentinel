#!/usr/bin/env python3
"""CI acceptance policy for independently verified comparisons.

This module does NOT verify evidence or authenticate execution.
Only a trusted verifier may pass comparison verdicts to it.
"""

import re

VERSION = "1"

MATRIX = {
    "STILL_SATISFIED": ("PASS", "RESTRICTION_PRESERVED"),
    "CHANGED_TO_VIOLATION": ("BLOCK", "NEW_VIOLATION"),
    "STILL_VIOLATED": ("BLOCK", "EXISTING_VIOLATION"),
    "CHANGED_TO_SATISFIED": ("REVIEW", "REMEDIATION_REVIEW"),
    "INDETERMINATE": ("REVIEW", "INDETERMINATE"),
    "INCOMPARABLE": ("REVIEW", "INCOMPARABLE"),
}

IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9-]{0,127}\Z")


def verdict_decision(verdict):
    """Map an already verified comparison to policy decision."""
    if type(verdict) is not str or verdict not in MATRIX:
        return {
            "decision": "BLOCK",
            "reason": "UNKNOWN_VERDICT",
        }

    decision, reason = MATRIX[verdict]

    return {
        "decision": decision,
        "reason": reason,
    }


def blocked(reason):
    return {
        "decision": "BLOCK",
        "reason": reason,
        "scenarios": [],
    }


def aggregate(required, comparisons):
    """Aggregate trusted scenario inventory and verified verdicts.

    Inputs must originate from a trusted caller after verification.
    This function is not a standalone trust boundary.
    """
    if type(required) is not list or not required:
        return blocked("EMPTY_OR_INVALID_INVENTORY")

    if any(
        type(item) is not str or IDENT.fullmatch(item) is None
        for item in required
    ):
        return blocked("INVALID_SCENARIO_ID")

    if len(set(required)) != len(required):
        return blocked("DUPLICATE_REQUIRED_SCENARIO")

    if type(comparisons) is not list:
        return blocked("INVALID_COMPARISON_SET")

    seen = {}

    for item in comparisons:
        if type(item) is not dict or set(item) != {
            "id", "verdict"
        }:
            return blocked("INVALID_COMPARISON_ENTRY")

        scenario_id = item["id"]

        if type(scenario_id) is not str:
            return blocked("INVALID_COMPARISON_ENTRY")

        if scenario_id in seen:
            return blocked("DUPLICATE_COMPARISON")

        if scenario_id not in required:
            return blocked("UNEXPECTED_SCENARIO")

        seen[scenario_id] = item["verdict"]

    if len(seen) != len(required):
        return blocked("MISSING_REQUIRED_SCENARIO")

    scenarios = []

    for scenario_id in required:
        verdict = seen[scenario_id]
        result = verdict_decision(verdict)

        scenarios.append({
            "id": scenario_id,
            "verdict": verdict,
            **result,
        })

    decisions = {
        entry["decision"] for entry in scenarios
    }

    if "BLOCK" in decisions:
        decision = "BLOCK"
        reason = "SCENARIO_BLOCKED"
    elif "REVIEW" in decisions:
        decision = "REVIEW"
        reason = "SCENARIO_REQUIRES_REVIEW"
    else:
        decision = "PASS"
        reason = "ALL_REQUIRED_SCENARIOS_PASSED"

    return {
        "decision": decision,
        "reason": reason,
        "scenarios": scenarios,
    }
