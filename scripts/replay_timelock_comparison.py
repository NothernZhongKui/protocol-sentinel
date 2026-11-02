#!/usr/bin/env python3
"""Independent OZ Timelock comparison replay.

Frozen semantics: oz-timelock-single-v1.
No Foundry, RPC or trusted execution provenance is required.
"""

import argparse
import json
from pathlib import Path

from eth_abi import encode
from eth_hash.auto import keccak

from validate_comparison_schema import (
    load_document,
    validate_document,
)

ROOT = Path(__file__).resolve().parents[1]

REGISTRY = json.loads(
    (ROOT / "evidence/semantics/registry.json").read_text()
)

ROUTE = REGISTRY["routes"]["OZ_TIMELOCK_SINGLE"]

SLOT = bytes.fromhex(
    "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
)

ZERO32 = bytes(32)


class ReplayMismatch(ValueError):
    pass


class InvalidPreparation(ReplayMismatch):
    """Solidity InvalidTimelockPreparation, not policy FAIL."""

    def __init__(self, failure):
        self.failure = failure
        super().__init__(
            f"InvalidTimelockPreparation({failure})"
        )


def raw(value):
    return bytes.fromhex(value[2:])


def address_word(value):
    # Solidity: address(uint160(uint256(bytes32_word))).
    return raw(value)[-20:]


def same_hex(a, b):
    return raw(a) == raw(b)


def selector(signature):
    return keccak(signature.encode())[:4]


def ensure(actual, expected, label):
    if actual != expected:
        raise ReplayMismatch(
            f"{label}: recorded={actual!r}, expected={expected!r}"
        )


def decision(status, reason):
    return {"status": status, "reason": reason}


def identities(spec, scenario_id):
    """Compute all derived identities from declarations only."""

    property_ordinal = ROUTE["enums"][
        "TimelockProperty"
    ].index(spec["property"])

    inner = selector(
        ROUTE["innerCallSignature"]
    ) + encode(
        ["address", "address", "bytes"],
        [
            raw(spec["proxy"]),
            raw(spec["candidate"]),
            b"",
        ],
    )

    operation_values = [
        raw(spec["proxyAdmin"]),
        0,
        inner,
        raw(spec["predecessor"]),
        raw(spec["salt"]),
    ]

    operation_id = keccak(encode(
        ROUTE["operationIdAbiTypes"],
        operation_values,
    ))

    outer = selector(
        ROUTE["outerCallSignature"]
    ) + encode(
        ROUTE["operationIdAbiTypes"],
        operation_values,
    )

    scenario_tuple = (
        raw(spec["timelock"]),
        raw(spec["proposer"]),
        raw(spec["executor"]),
        raw(spec["proxyAdmin"]),
        raw(spec["proxy"]),
        raw(spec["candidate"]),
        raw(spec["predecessor"]),
        raw(spec["salt"]),
        property_ordinal,
    )

    scenario_key = keccak(encode(
        ROUTE["scenarioKeyAbiTypes"],
        [
            keccak(
                ROUTE["comparisonDomain"].encode()
            ),
            raw(scenario_id),
            scenario_tuple,
            operation_id,
            outer,
            SLOT,
        ],
    ))

    return {
        "innerCalldata": inner,
        "outerCalldata": outer,
        "operationId": operation_id,
        "scenarioKey": scenario_key,
    }


def matches_scenario(spec, obs, derived):
    """Exact frozen _matchesRoutedScenario semantics."""

    return (
        same_hex(obs["executor"], spec["executor"])
        and same_hex(obs["txOrigin"], spec["executor"])
        and same_hex(obs["outerTarget"], spec["timelock"])
        and same_hex(obs["timelock"], spec["timelock"])
        and same_hex(obs["proxyAdmin"], spec["proxyAdmin"])
        and same_hex(obs["predecessor"], spec["predecessor"])
        and raw(obs["operationId"]) == derived["operationId"]
        and raw(obs["observedSlot"]) == SLOT
        and raw(obs["outerCallData"]) == derived["outerCalldata"]
    )


def evaluate(spec, obs, derived):
    """Exact _evaluateTimelockRoute branch precedence."""

    if not matches_scenario(spec, obs, derived):
        return decision("UNKNOWN", "CONTEXT_MISMATCH")

    predecessor_exists = raw(spec["predecessor"]) != ZERO32

    if (
        not obs["operationStateBeforeObserved"]
        or not obs["executorEOAObserved"]
        or not obs["proxyCodeObserved"]
        or not obs["candidateCodeObserved"]
        or not obs["proxyAdminOwnershipObserved"]
        or not obs["executorRolesObserved"]
        or (
            predecessor_exists
            and not obs["predecessorStateObserved"]
        )
    ):
        return decision("UNKNOWN", "INCOMPLETE_EVIDENCE")

    state = obs["operationStateBefore"]

    timestamp = int(obs["observedTimestamp"])
    ready_at = int(obs["readyAt"])

    if (
        (
            state == "Waiting"
            and (ready_at <= timestamp or ready_at <= 1)
        )
        or (
            state == "Ready"
            and (ready_at > timestamp or ready_at <= 1)
        )
        or (state == "Unset" and ready_at != 0)
        or (state == "Done" and ready_at != 1)
    ):
        return decision("UNKNOWN", "INCONSISTENT_TIMING")

    if obs["operationDoneBefore"] != (state == "Done"):
        return decision(
            "UNKNOWN",
            "INCONSISTENT_EXECUTION",
        )

    ready_property = (
        spec["property"] == "READY_UPGRADE_SUCCEEDS"
    )

    required_state = "Ready" if ready_property else "Waiting"

    if state != required_state:
        raise InvalidPreparation("WRONG_OPERATION_STATE")

    if (
        raw(spec["executor"]) == bytes(20)
        or not obs["executorEOAValid"]
    ):
        raise InvalidPreparation("INVALID_EOA_EXECUTOR")

    if not (
        obs["executorHasRole"]
        or obs["openExecutorRole"]
    ):
        raise InvalidPreparation("INELIGIBLE_EXECUTOR")

    if predecessor_exists and not obs["predecessorDoneBefore"]:
        raise InvalidPreparation("UNFINISHED_PREDECESSOR")

    if not obs["proxyAdminOwnedByTimelock"]:
        raise InvalidPreparation("INVALID_PROXY_ADMIN")

    before = address_word(obs["implementationBefore"])
    after = address_word(obs["implementationAfter"])

    if not obs["proxyHasCode"] or before == bytes(20):
        raise InvalidPreparation("INVALID_PROXY")

    if not obs["candidateHasCode"]:
        raise InvalidPreparation("INVALID_CANDIDATE")

    if ready_property and before == raw(spec["candidate"]):
        raise InvalidPreparation("NO_IMPLEMENTATION_CHANGE")

    return_data = raw(obs["returnData"])

    if obs["outerSuccess"] and len(return_data) != 0:
        return decision(
            "UNKNOWN",
            "INCONSISTENT_EXECUTION",
        )

    if not obs["outerSuccess"]:
        if obs["operationDoneAfter"] or after != before:
            return decision(
                "UNKNOWN",
                "INCONSISTENT_EXECUTION",
            )

        if ready_property:
            return decision(
                "FAIL",
                "EXECUTION_REJECTED",
            )

        expected_revert = selector(
            "TimelockUnexpectedOperationState(bytes32,bytes32)"
        ) + encode(
            ["bytes32", "bytes32"],
            [
                derived["operationId"],
                (4).to_bytes(32, "big"),
            ],
        )

        if return_data == expected_revert:
            return decision("PASS", "NONE")

        return decision("UNKNOWN", "UNEXPECTED_REVERT")

    if not obs["operationDoneAfter"]:
        return decision(
            "UNKNOWN",
            "INCONSISTENT_EXECUTION",
        )

    if not ready_property:
        return decision("FAIL", "NONE")

    if after != raw(spec["candidate"]):
        return decision(
            "FAIL",
            "MISSING_UPGRADE_EFFECT",
        )

    return decision("PASS", "NONE")


def same_preparation(spec, before, after):
    """Exact _sameRoutedPreparation semantics."""

    if int(before["readyAt"]) != int(after["readyAt"]):
        return False

    if (
        before["executorRolesObserved"]
        and after["executorRolesObserved"]
    ):
        if (
            before["executorHasRole"]
            != after["executorHasRole"]
            or before["openExecutorRole"]
            != after["openExecutorRole"]
        ):
            return False

    if (
        before["proxyAdminOwnershipObserved"]
        and after["proxyAdminOwnershipObserved"]
        and before["proxyAdminOwnedByTimelock"]
        != after["proxyAdminOwnedByTimelock"]
    ):
        return False

    if (
        raw(spec["predecessor"]) != ZERO32
        and before["predecessorStateObserved"]
        and after["predecessorStateObserved"]
        and before["predecessorDoneBefore"]
        != after["predecessorDoneBefore"]
    ):
        return False

    return True


def compare(spec, stages, evaluations, derived):
    """Exact _compareTimelockRoute branch precedence."""

    before_stage = stages["before"]
    after_stage = stages["after"]

    before = before_stage["observation"]
    after = after_stage["observation"]

    bs = evaluations["before"]["status"]
    a_s = evaluations["after"]["status"]

    if bs == "ERROR" or a_s == "ERROR":
        raise ReplayMismatch("InvalidComparisonPolicyStatus")

    if (
        not matches_scenario(spec, before, derived)
        or not matches_scenario(spec, after, derived)
    ):
        return "INCOMPARABLE", "SCENARIO_MISMATCH"

    if (
        address_word(before["implementationBefore"])
        != raw(before_stage["expectedActiveImplementation"])
        or address_word(after["implementationBefore"])
        != raw(after_stage["expectedActiveImplementation"])
    ):
        return "INCOMPARABLE", "STAGE_BINDING_MISMATCH"

    if same_hex(
        before_stage["expectedActiveImplementation"],
        after_stage["expectedActiveImplementation"],
    ):
        return "INCOMPARABLE", "SAME_IMPLEMENTATION_STAGE"

    if not same_preparation(spec, before, after):
        return "INCOMPARABLE", "PREPARATION_MISMATCH"

    if bs == "UNKNOWN" or a_s == "UNKNOWN":
        return "INDETERMINATE", "INDETERMINATE_POLICY"

    transitions = {
        ("PASS", "PASS"): "STILL_SATISFIED",
        ("PASS", "FAIL"): "CHANGED_TO_VIOLATION",
        ("FAIL", "PASS"): "CHANGED_TO_SATISFIED",
        ("FAIL", "FAIL"): "STILL_VIOLATED",
    }

    pair = (bs, a_s)

    if pair not in transitions:
        raise ReplayMismatch(
            f"Unsupported policy transition: {pair}"
        )

    return transitions[pair], "NONE"


def replay(document):
    validate_document(document)

    if document["route"] != "OZ_TIMELOCK_SINGLE":
        raise ReplayMismatch("Unsupported route")

    if document["semantics_version"] != ROUTE["semanticsVersion"]:
        raise ReplayMismatch("Unsupported semantics version")

    scenario = document["scenario"]
    spec = scenario["spec"]

    derived = identities(spec, scenario["scenarioId"])

    for name in (
        "innerCalldata",
        "outerCalldata",
        "operationId",
    ):
        ensure(
            raw(scenario["derived"][name]),
            derived[name],
            f"Derived {name}",
        )

    ensure(
        raw(document["comparison"]["scenarioKey"]),
        derived["scenarioKey"],
        "Scenario key",
    )

    stages = document["stages"]
    evaluations = {}

    # Solidity evaluates before first, then after.
    # Invalid preparation aborts the completed comparison.
    for name in ("before", "after"):
        calculated = evaluate(
            spec,
            stages[name]["observation"],
            derived,
        )

        ensure(
            stages[name]["evaluation"],
            calculated,
            f"{name} evaluation",
        )

        evaluations[name] = calculated

    verdict, reason = compare(
        spec,
        stages,
        evaluations,
        derived,
    )

    ensure(
        document["comparison"]["verdict"],
        verdict,
        "Comparison verdict",
    )

    ensure(
        document["comparison"]["reason"],
        reason,
        "Comparison reason",
    )

    return {
        "schema": "VALID",
        "classification_replay": "MATCH",
        "before": evaluations["before"],
        "after": evaluations["after"],
        "comparison": verdict,
        "comparison_reason": reason,
        "source_context": "NOT_CHECKED",
        "execution_provenance": "UNAUTHENTICATED",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()

    try:
        doc = load_document(args.evidence)
        report = replay(doc)
    except InvalidPreparation as exc:
        parser.exit(1, f"INVALID_PREPARATION | {exc}\n")
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"REPLAY MISMATCH | {exc}\n")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
