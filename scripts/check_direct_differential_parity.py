#!/usr/bin/env python3
"""Check Solidity/Python parity over identical Direct Evidence inputs.

The Solidity oracle is produced separately from this checker.
No Solidity classification is used to calculate Python expectations.
"""

import argparse
import copy
import json
import sys
from pathlib import Path

from eth_hash.auto import keccak

from replay_direct_comparison import (
    ROUTE,
    canonical_call,
    compare,
    evaluate,
    replay,
)
from validate_comparison_schema import load_document

CASES = (
    "baseline",
    "slot_context",
    "invalid_target",
    "wrong_revert",
    "stage_binding",
    "scenario_precedence",
    "upper_bits",
    "same_impl",
    "both_pass",
    "both_fail",
    "fail_to_pass",
    "success_no_replacement",
    "invalid_candidate",
)

POLICIES = (
    ("replacement", "NO_IMPLEMENTATION_REPLACEMENT"),
    ("successful_call", "NO_SUCCESSFUL_UPGRADE_CALL"),
)

FIELDS = (
    "before_status",
    "before_reason",
    "after_status",
    "after_reason",
    "verdict",
    "comparison_reason",
)

ENUMS = ROUTE["enums"]


class DifferentialMismatch(ValueError):
    pass


def require(condition, description):
    if not condition:
        raise DifferentialMismatch(description)


def address(number):
    return "0x" + format(number, "040x")


def with_upper_bit(value, position):
    number = int(value, 16)
    number |= 1 << position

    return "0x" + format(number, "064x")


def mutated_stages(document, name):
    # An independent copy for every Solidity mutation case.
    stages = copy.deepcopy(document["stages"])

    before = stages["before"]
    after = stages["after"]

    b = before["observation"]
    a = after["observation"]

    if name == "baseline":
        pass

    elif name == "slot_context":
        b["observedSlot"] = "0x" + "00" * 32
        b["actor"] = address(0xBEEF)

    elif name == "invalid_target":
        b["targetValidAtObservation"] = False
        b["candidateValidAtObservation"] = False

    elif name == "wrong_revert":
        b["returnData"] = "0xdeadbeef"

    elif name == "stage_binding":
        after["expectedActiveImplementation"] = address(
            0xBEEF
        )

    elif name == "scenario_precedence":
        b["targetValidAtObservation"] = False
        a["callData"] = "0xdeadbeef"

    elif name == "upper_bits":
        b["implementationBefore"] = with_upper_bit(
            b["implementationBefore"],
            200,
        )

        a["implementationBefore"] = with_upper_bit(
            a["implementationBefore"],
            201,
        )

    elif name == "same_impl":
        after["expectedActiveImplementation"] = (
            before["expectedActiveImplementation"]
        )

        a["implementationBefore"] = (
            b["implementationBefore"]
        )

    elif name == "both_pass":
        a["success"] = False
        a["returnData"] = b["returnData"]
        a["implementationAfter"] = a["implementationBefore"]

    elif name == "both_fail":
        b["success"] = True
        b["returnData"] = "0x"
        b["implementationAfter"] = a["implementationAfter"]

    elif name == "fail_to_pass":
        a["success"] = False
        a["returnData"] = b["returnData"]
        a["implementationAfter"] = a["implementationBefore"]

        b["success"] = True
        b["returnData"] = "0x"
        b["implementationAfter"] = document["stages"]["after"]["observation"]["implementationAfter"]

    elif name == "success_no_replacement":
        a["implementationAfter"] = a["implementationBefore"]

    elif name == "invalid_candidate":
        b["candidateValidAtObservation"] = False

    else:
        raise DifferentialMismatch(
            f"Unknown mutation case: {name}"
        )

    return stages


def ordinal(enum_name, value):
    values = ENUMS[enum_name]

    require(
        value in values,
        f"{enum_name}: unknown value {value}",
    )

    return values.index(value)


def python_classification(document, name, policy):
    spec = copy.deepcopy(document["scenario"]["spec"])
    spec["policy"] = policy

    stages = mutated_stages(document, name)

    calldata = canonical_call(spec)

    evaluations = {
        stage: evaluate(
            spec,
            stages[stage]["observation"],
            calldata,
        )
        for stage in ("before", "after")
    }

    verdict, reason = compare(
        spec,
        stages,
        evaluations,
        calldata,
    )

    return {
        "before_status": ordinal(
            "PolicyStatus",
            evaluations["before"]["status"],
        ),
        "before_reason": ordinal(
            "PolicyReason",
            evaluations["before"]["reason"],
        ),
        "after_status": ordinal(
            "PolicyStatus",
            evaluations["after"]["status"],
        ),
        "after_reason": ordinal(
            "PolicyReason",
            evaluations["after"]["reason"],
        ),
        "verdict": ordinal(
            "ComparisonVerdict",
            verdict,
        ),
        "comparison_reason": ordinal(
            "ComparisonReason",
            reason,
        ),
    }


def check(document, oracle, evidence_path):
    # This verifies the original published classification
    # before applying any synthetic mutations.
    original = replay(document)

    require(
        original["classification_replay"] == "MATCH",
        "Original evidence replay failed",
    )

    require(
        document["route"] == "DIRECT_EOA_UUPS",
        "Wrong route",
    )

    require(
        oracle["format"]
        == "protocol-sentinel-direct-differential-v2",
        "Wrong oracle format",
    )

    require(
        oracle["scenario_key"]
        == document["comparison"]["scenarioKey"],
        "Solidity oracle does not belong to this evidence",
    )

    require(
        oracle["evidence_keccak"].lower()
        == "0x" + keccak(evidence_path.read_bytes()).hex(),
        "Evidence input hash mismatch",
    )

    expected_fields = {"format", "scenario_key", "evidence_keccak"}

    for prefix, _ in POLICIES:
        for name in CASES:
            expected_fields.update(
                f"{prefix}_{name}_{field}" for field in FIELDS
            )

    require(
        set(oracle) == expected_fields,
        "Missing or unexpected oracle fields",
    )

    matches = 0

    expectations = {
        "baseline": ("PASS", "FAIL", "CHANGED_TO_VIOLATION"),
        "both_pass": ("PASS", "PASS", "STILL_SATISFIED"),
        "both_fail": ("FAIL", "FAIL", "STILL_VIOLATED"),
        "fail_to_pass": ("FAIL", "PASS", "CHANGED_TO_SATISFIED"),
        "invalid_candidate": ("UNKNOWN", "FAIL", "INDETERMINATE"),
        "stage_binding": ("PASS", "FAIL", "INCOMPARABLE"),
    }

    for prefix, policy in POLICIES:
        for name in CASES:
            calculated = python_classification(document, name, policy)

            expected = expectations.get(name)

            if name == "success_no_replacement":
                if prefix == "replacement":
                    expected = ("PASS", "UNKNOWN", "INDETERMINATE")
                    expected_reason = "SUCCESS_WITHOUT_REPLACEMENT"
                else:
                    expected = ("PASS", "FAIL", "CHANGED_TO_VIOLATION")
                    expected_reason = "NONE"

                require(
                    calculated["after_reason"] ==
                    ordinal("PolicyReason", expected_reason),
                    f"{prefix}_{name}: wrong diagnostic reason",
                )

            if expected is not None:
                for field, enum_name, symbolic in zip(
                    ("before_status", "after_status", "verdict"),
                    ("PolicyStatus", "PolicyStatus", "ComparisonVerdict"),
                    expected,
                ):
                    require(
                        calculated[field] == ordinal(enum_name, symbolic),
                        f"{prefix}_{name}: unexpected {field}",
                    )

            for field in FIELDS:
                key = f"{prefix}_{name}_{field}"
                expected_value = calculated[field]
                actual = oracle[key]

                require(
                    type(actual) is int,
                    f"{key}: non-integer oracle result",
                )

                require(
                    actual == expected_value,
                    f"{key}: Solidity={actual}, Python={expected_value}",
                )

                matches += 1

        print(f"PASS | {prefix}: {len(CASES)} differential cases")

    require(matches == 156, "Incomplete Direct differential matrix")

    print()
    print("DIFFERENTIAL PARITY: 156/156 MATCH")
    print("PASS | Both Direct policies and all definitive transitions")
    print("PASS | Independent Direct comparison replay")

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--evidence",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--oracle",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    try:
        document = load_document(args.evidence)
        oracle = load_document(args.oracle)
        check(document, oracle, args.evidence)

    except (
        DifferentialMismatch,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        parser.exit(
            1,
            f"DIFFERENTIAL MISMATCH | {exc}\n",
        )


if __name__ == "__main__":
    main()
