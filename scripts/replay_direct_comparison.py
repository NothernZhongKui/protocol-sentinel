#!/usr/bin/env python3
"""Independent direct comparison replay for frozen direct-eoa-v1."""

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

ROUTE = REGISTRY["routes"]["DIRECT_EOA_UUPS"]

SLOT = bytes.fromhex(
    "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
)


class ReplayMismatch(ValueError):
    pass


def raw(value):
    return bytes.fromhex(value[2:])


def ensure(actual, expected, label):
    if actual != expected:
        raise ReplayMismatch(
            f"{label}: expected {expected!r}, recorded {actual!r}"
        )


def implementation(word):
    # Solidity: address(uint160(uint256(bytes32_word)))
    return raw(word)[-20:]


def canonical_call(spec):
    signature = ROUTE["callSignature"]

    return keccak(signature.encode())[:4] + encode(
        ["address", "bytes"],
        [raw(spec["candidate"]), b""],
    )


def scenario_key(scenario_id, spec, calldata):
    policy = ROUTE["enums"]["UpgradePolicy"].index(
        spec["policy"]
    )

    domain = keccak(ROUTE["comparisonDomain"].encode())

    return keccak(encode(
        ROUTE["scenarioKeyAbiTypes"],
        [
            domain,
            raw(scenario_id),
            raw(spec["actor"]),
            raw(spec["target"]),
            raw(spec["candidate"]),
            calldata,
            raw(spec["expectedRevert"]),
            policy,
            SLOT,
        ],
    ))


def decision(status, reason):
    return {"status": status, "reason": reason}


def evaluate(spec, obs, calldata):
    """Frozen AuthorityProbe._evaluateUpgradePolicyDetailed order."""

    if raw(obs["observedSlot"]) != SLOT:
        return decision("UNKNOWN", "INVALID_SLOT")

    if (
        raw(obs["actor"]) != raw(spec["actor"])
        or raw(obs["txOrigin"]) != raw(spec["actor"])
        or raw(obs["target"]) != raw(spec["target"])
    ):
        return decision("UNKNOWN", "CONTEXT_MISMATCH")

    if not obs["targetValidAtObservation"]:
        return decision("UNKNOWN", "INVALID_TARGET")

    if raw(obs["callData"]) != calldata:
        return decision("UNKNOWN", "NON_CANONICAL_CALLDATA")

    unchanged = (
        implementation(obs["implementationBefore"])
        == implementation(obs["implementationAfter"])
    )

    if not obs["success"]:
        if not obs["candidateValidAtObservation"]:
            return decision("UNKNOWN", "INVALID_CANDIDATE")

        expected_revert = raw(spec["expectedRevert"])

        if (
            unchanged
            and len(expected_revert) > 0
            and raw(obs["returnData"]) == expected_revert
        ):
            return decision("PASS", "NONE")

        return decision("UNKNOWN", "UNEXPECTED_REVERT")

    if spec["policy"] == "NO_SUCCESSFUL_UPGRADE_CALL":
        return decision("FAIL", "NONE")

    if not unchanged:
        return decision("FAIL", "NONE")

    return decision(
        "UNKNOWN",
        "SUCCESS_WITHOUT_REPLACEMENT",
    )


def matches_scenario(spec, obs, calldata):
    return (
        raw(obs["actor"]) == raw(spec["actor"])
        and raw(obs["txOrigin"]) == raw(spec["actor"])
        and raw(obs["target"]) == raw(spec["target"])
        and raw(obs["observedSlot"]) == SLOT
        and raw(obs["callData"]) == calldata
    )


def compare(spec, stages, evaluations, calldata):
    """Frozen ComparativeAuthorityProbe._compareDirectUpgrade order."""

    before = stages["before"]
    after = stages["after"]

    bs = evaluations["before"]["status"]
    a_s = evaluations["after"]["status"]

    if bs == "ERROR" or a_s == "ERROR":
        raise ReplayMismatch("Invalid completed PolicyStatus.ERROR")

    if (
        not matches_scenario(
            spec, before["observation"], calldata
        )
        or not matches_scenario(
            spec, after["observation"], calldata
        )
    ):
        return "INCOMPARABLE", "SCENARIO_MISMATCH"

    if (
        implementation(
            before["observation"]["implementationBefore"]
        ) != raw(before["expectedActiveImplementation"])
        or implementation(
            after["observation"]["implementationBefore"]
        ) != raw(after["expectedActiveImplementation"])
    ):
        return "INCOMPARABLE", "STAGE_BINDING_MISMATCH"

    if (
        raw(before["expectedActiveImplementation"])
        == raw(after["expectedActiveImplementation"])
    ):
        return "INCOMPARABLE", "SAME_IMPLEMENTATION_STAGE"

    if bs == "UNKNOWN" or a_s == "UNKNOWN":
        return "INDETERMINATE", "INDETERMINATE_POLICY"

    transitions = {
        ("PASS", "PASS"): "STILL_SATISFIED",
        ("PASS", "FAIL"): "CHANGED_TO_VIOLATION",
        ("FAIL", "PASS"): "CHANGED_TO_SATISFIED",
        ("FAIL", "FAIL"): "STILL_VIOLATED",
    }

    key = (bs, a_s)

    if key not in transitions:
        raise ReplayMismatch(f"Unsupported status transition: {key}")

    return transitions[key], "NONE"


def replay(doc, *, schema=None):
    # Legacy Evidence uses frozen v1 by default. v0.6 callers must
    # explicitly pass a separately validated versioned schema.
    validate_document(doc, schema=schema)

    if doc["route"] != "DIRECT_EOA_UUPS":
        raise ReplayMismatch("This replay supports direct route only")

    if doc["semantics_version"] != ROUTE["semanticsVersion"]:
        raise ReplayMismatch("Unsupported direct semantics version")

    scenario = doc["scenario"]
    spec = scenario["spec"]
    stages = doc["stages"]

    calldata = canonical_call(spec)

    ensure(
        raw(scenario["derived"]["canonicalCalldata"]),
        calldata,
        "Declared canonical calldata",
    )

    expected_key = scenario_key(
        scenario["scenarioId"],
        spec,
        calldata,
    )

    ensure(
        raw(doc["comparison"]["scenarioKey"]),
        expected_key,
        "Scenario key",
    )

    evaluations = {}

    for stage_name in ("before", "after"):
        stage = stages[stage_name]

        actual = evaluate(
            spec,
            stage["observation"],
            calldata,
        )

        ensure(
            stage["evaluation"],
            actual,
            f"{stage_name} policy evaluation",
        )

        evaluations[stage_name] = actual

    verdict, reason = compare(
        spec,
        stages,
        evaluations,
        calldata,
    )

    ensure(
        doc["comparison"]["verdict"],
        verdict,
        "Comparison verdict",
    )

    ensure(
        doc["comparison"]["reason"],
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
        document = load_document(args.evidence)
        report = replay(document)
    except (ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"REPLAY FAILED | {exc}\n")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
