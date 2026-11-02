#!/usr/bin/env python3
"""Independent parity with Solidity Timelock differential oracle."""

import argparse
import copy
import json
from pathlib import Path

from eth_abi import encode

from replay_timelock_comparison import (
    REGISTRY, ROUTE, InvalidPreparation,
    compare, evaluate, identities, replay, selector,
)
from validate_comparison_schema import load_document

NAMES = (
    "baseline", "context_precedence", "missing_evidence",
    "timing_precedence", "inconsistent_done", "role_drift",
    "reschedule", "unknown_vs_preparation", "wrong_return_data",
    "upper_bits", "stage_binding", "wrong_state",
    "invalid_eoa", "ineligible_executor", "invalid_admin",
    "predecessor_unfinished", "no_implementation_change",
    "invalid_candidate", "invalid_proxy",
    "predecessor_completed", "same_impl",
)

FIELDS = (
    "before_status", "before_reason", "after_status",
    "after_reason", "verdict", "comparison_reason",
)

COMMON = REGISTRY["routes"]["DIRECT_EOA_UUPS"]["enums"]
ROUTED = ROUTE["enums"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ordinal(mapping, enum, value):
    return mapping[enum].index(value)


def predecessor(spec, stages, scenario_id):
    spec["predecessor"] = "0x" + format(0x1234, "064x")
    derived = identities(spec, scenario_id)

    operation = "0x" + derived["operationId"].hex()
    calldata = "0x" + derived["outerCalldata"].hex()

    for stage in stages.values():
        obs = stage["observation"]
        obs["predecessor"] = spec["predecessor"]
        obs["operationId"] = operation
        obs["outerCallData"] = calldata
        obs["predecessorStateObserved"] = True
        obs["predecessorDoneBefore"] = True

        if spec["property"] == "NOT_READY_EXECUTION_REJECTED":
            revert = selector(
                "TimelockUnexpectedOperationState(bytes32,bytes32)"
            ) + encode(
                ["bytes32", "bytes32"],
                [derived["operationId"], (4).to_bytes(32, "big")],
            )
            obs["returnData"] = "0x" + revert.hex()


def mutate(document, index):
    spec = copy.deepcopy(document["scenario"]["spec"])
    stages = copy.deepcopy(document["stages"])
    b = stages["before"]["observation"]
    a = stages["after"]["observation"]
    ready = spec["property"] == "READY_UPGRADE_SUCCEEDS"

    if index == 1:
        b["outerTarget"] = "0x" + format(0xBEEF, "040x")
        b["executorRolesObserved"] = False
    elif index == 2:
        b["executorRolesObserved"] = False
        b["executorEOAValid"] = False
    elif index == 3:
        b["readyAt"] = str(
            int(b["observedTimestamp"]) + (10 if ready else 0)
        )
        b["executorHasRole"] = False
        b["openExecutorRole"] = False
    elif index == 4:
        b["operationDoneBefore"] = True
    elif index == 5:
        a["openExecutorRole"] = not a["openExecutorRole"]
    elif index in (6, 7):
        if index == 7:
            b["executorRolesObserved"] = False
        a["readyAt"] = str(int(a["readyAt"]) + 10)
        if ready:
            a["observedTimestamp"] = a["readyAt"]
    elif index == 8:
        b["returnData"] = "0xdeadbeef"
    elif index == 9:
        for obs, bit in ((b, 200), (a, 201)):
            obs["implementationBefore"] = (
                "0x" + format(
                    int(obs["implementationBefore"], 16) | (1 << bit),
                    "064x",
                )
            )
    elif index == 10:
        stages["after"]["expectedActiveImplementation"] = (
            "0x" + format(0xBEEF, "040x")
        )
    elif index == 11:
        b["operationStateBefore"] = "Waiting" if ready else "Ready"
        b["readyAt"] = str(
            int(b["observedTimestamp"]) + (100 if ready else 0)
        )
        b["executorHasRole"] = False
        b["openExecutorRole"] = False
    elif index == 12:
        b["executorEOAValid"] = False
    elif index == 13:
        b["executorHasRole"] = False
        b["openExecutorRole"] = False
    elif index == 14:
        b["proxyAdminOwnedByTimelock"] = False
    elif index == 15:
        predecessor(spec, stages, document["scenario"]["scenarioId"])
        b["predecessorDoneBefore"] = False
    elif index == 16:
        b["implementationBefore"] = (
            "0x" + format(int(spec["candidate"], 16), "064x")
        )
    elif index == 17:
        b["candidateHasCode"] = False
    elif index == 18:
        b["proxyHasCode"] = False
    elif index == 19:
        predecessor(spec, stages, document["scenario"]["scenarioId"])
    elif index == 20:
        stages["after"]["expectedActiveImplementation"] = (
            stages["before"]["expectedActiveImplementation"]
        )
        a["implementationBefore"] = b["implementationBefore"]
        a["implementationAfter"] = b["implementationAfter"]
    else:
        require(index == 0, "Unknown mutation index")

    return spec, stages


def check_case(document, oracle, label, index):
    name = NAMES[index]
    prefix = f"{label}_{name}"
    kind = oracle[f"{prefix}_kind"]

    spec, stages = mutate(document, index)
    derived = identities(spec, document["scenario"]["scenarioId"])

    try:
        evaluations = {
            stage: evaluate(
                spec, stages[stage]["observation"], derived
            )
            for stage in ("before", "after")
        }

        verdict, reason = compare(
            spec, stages, evaluations, derived
        )

    except InvalidPreparation as exc:
        require(
            kind == "INVALID_PREPARATION",
            f"{prefix}: Solidity compared, Python aborted",
        )

        failure = ordinal(
            ROUTED, "PreparationFailure", exc.failure
        )

        require(
            oracle[f"{prefix}_failure"] == failure,
            f"{prefix}_failure: Solidity="
            f"{oracle[f'{prefix}_failure']}, Python={failure}",
        )

        return "preparation"

    require(
        kind == "COMPARED",
        f"{prefix}: Solidity aborted, Python compared",
    )

    expected = {
        "before_status": ordinal(
            COMMON, "PolicyStatus", evaluations["before"]["status"]
        ),
        "before_reason": ordinal(
            ROUTED, "RoutedReason", evaluations["before"]["reason"]
        ),
        "after_status": ordinal(
            COMMON, "PolicyStatus", evaluations["after"]["status"]
        ),
        "after_reason": ordinal(
            ROUTED, "RoutedReason", evaluations["after"]["reason"]
        ),
        "verdict": ordinal(
            COMMON, "ComparisonVerdict", verdict
        ),
        "comparison_reason": ordinal(
            ROUTED, "RoutedComparisonReason", reason
        ),
    }

    for field in FIELDS:
        key = f"{prefix}_{field}"
        require(
            type(oracle[key]) is int and oracle[key] == expected[field],
            f"{key}: Solidity={oracle[key]}, Python={expected[field]}",
        )

    return "compared"


def check(ready, waiting, oracle):
    require(
        oracle["format"] ==
        "protocol-sentinel-routed-differential-v1",
        "Wrong oracle format",
    )

    expected_keys = {"format"}
    counts = {"compared": 0, "preparation": 0}

    for label, document, prop in (
        ("ready", ready, "READY_UPGRADE_SUCCEEDS"),
        ("waiting", waiting, "NOT_READY_EXECUTION_REJECTED"),
    ):
        require(
            document["scenario"]["spec"]["property"] == prop,
            f"{label}: wrong fixture",
        )

        require(
            replay(document)["classification_replay"] == "MATCH",
            f"{label}: baseline replay failed",
        )

        key = f"{label}_scenario_key"
        expected_keys.add(key)

        require(
            oracle[key].lower()
            == document["comparison"]["scenarioKey"].lower(),
            f"{label}: oracle scenario identity mismatch",
        )

        for index, name in enumerate(NAMES):
            prefix = f"{label}_{name}"
            expected_keys.add(f"{prefix}_kind")

            kind = oracle[f"{prefix}_kind"]

            if kind == "COMPARED":
                expected_keys.update(
                    f"{prefix}_{field}" for field in FIELDS
                )
            elif kind == "INVALID_PREPARATION":
                expected_keys.add(f"{prefix}_failure")
            else:
                raise ValueError(f"{prefix}: invalid oracle kind")

            counts[check_case(document, oracle, label, index)] += 1

        print(f"PASS | {label.upper()}: 21/21 cases")

    require(
        set(oracle) == expected_keys,
        "Oracle has missing or unexpected fields",
    )

    require(
        counts == {"compared": 27, "preparation": 15},
        f"Unexpected case counts: {counts}",
    )

    print(
        "PASS | 27 comparisons, 15 preparation errors"
    )
    print(
        "PASS | 162 comparison fields + 15 failure codes"
    )
    print("TIMELOCK DIFFERENTIAL PARITY: 42/42 MATCH")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--waiting", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    args = parser.parse_args()

    try:
        check(
            load_document(args.ready),
            load_document(args.waiting),
            load_document(args.oracle),
        )
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"DIFFERENTIAL MISMATCH | {exc}\n")


if __name__ == "__main__":
    main()
