#!/usr/bin/env python3
"""Replay AuthorityProbe verdict from saved JSON. No EVM execution."""

import json
import sys
from pathlib import Path

ERC1967_SLOT = int(
    "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",
    16,
)

UPGRADE_SELECTOR = bytes.fromhex("4f1ef286")
ADDRESS_MASK = (1 << 160) - 1

POLICIES = {
    "NO_IMPLEMENTATION_REPLACEMENT",
    "NO_SUCCESSFUL_UPGRADE_CALL",
}


def read_bytes(data, key, size=None):
    value = data[key]

    if (
        not isinstance(value, str)
        or not value.startswith("0x")
        or len(value[2:]) % 2 != 0
        or any(c not in "0123456789abcdefABCDEF" for c in value[2:])
        or (size is not None and len(value[2:]) != size * 2)
    ):
        raise ValueError(f"Invalid hex field: {key}")

    return bytes.fromhex(value[2:])


def word(data, key):
    return int.from_bytes(read_bytes(data, key, 32), "big")


def address(data, key):
    return int.from_bytes(read_bytes(data, key, 20), "big")


def flag(data, key):
    value = data[key]

    if type(value) is not bool:
        raise ValueError(f"Invalid boolean field: {key}")

    return value


def evaluate(data):
    policy = data["policy_rule"]

    if policy not in POLICIES:
        raise ValueError(f"Unsupported policy: {policy}")

    slot = word(data, "observed_slot")

    actor = address(data, "actor")
    origin = address(data, "tx_origin")
    target = address(data, "target")

    expected_actor = address(data, "expected_actor")
    expected_target = address(data, "expected_target")

    candidate = word(data, "expected_implementation") & ADDRESS_MASK

    calldata = read_bytes(data, "calldata")

    before = word(data, "implementation_before") & ADDRESS_MASK
    after = word(data, "implementation_after") & ADDRESS_MASK

    success = flag(data, "call_success")
    candidate_valid = flag(data, "candidate_valid_at_observation")

    return_data = read_bytes(data, "return_data")
    expected_revert = read_bytes(data, "expected_revert")

    # Observation identity and direct EOA context.
    if slot != ERC1967_SLOT:
        return "UNKNOWN"

    if (
        actor != expected_actor
        or origin != expected_actor
        or target != expected_target
    ):
        return "UNKNOWN"

    # Canonical upgradeToAndCall(address,bytes) with empty data.
    canonical = (
        UPGRADE_SELECTOR
        + candidate.to_bytes(32, "big")
        + (64).to_bytes(32, "big")
        + (0).to_bytes(32, "big")
    )

    if calldata != canonical:
        return "UNKNOWN"

    # Compare effective implementation addresses, not storage words.
    unchanged = before == after

    if not success:
        if not candidate_valid:
            return "UNKNOWN"

        if unchanged and return_data == expected_revert:
            return "PASS"

        return "UNKNOWN"

    # A confirmed successful call takes precedence over candidate checks.
    if policy == "NO_SUCCESSFUL_UPGRADE_CALL":
        return "FAIL"

    if not unchanged:
        return "FAIL"

    return "UNKNOWN"


def self_test(baseline):
    cases = []

    def add(name, expected, **changes):
        data = dict(baseline)
        data.update(changes)
        cases.append((name, expected, data))

    add("Original exported FAIL", "FAIL")

    add(
        "P1: candidate precedence",
        "FAIL",
        candidate_valid_at_observation=False,
    )

    add(
        "Origin mismatch",
        "UNKNOWN",
        tx_origin="0x" + "00" * 20,
    )

    add(
        "Target mismatch",
        "UNKNOWN",
        expected_target="0x" + "00" * 20,
    )

    add(
        "Incorrect implementation slot",
        "UNKNOWN",
        observed_slot="0x" + "00" * 32,
    )

    add(
        "Unrelated calldata",
        "UNKNOWN",
        calldata="0x",
    )

    high_bit_word = "0x" + format(
        int(baseline["implementation_before"], 16) ^ (1 << 200),
        "064x",
    )

    add(
        "P2: high bits, replacement policy",
        "UNKNOWN",
        implementation_after=high_bit_word,
    )

    add(
        "P2: high bits, successful-call policy",
        "FAIL",
        implementation_after=high_bit_word,
        policy_rule="NO_SUCCESSFUL_UPGRADE_CALL",
    )

    add(
        "Expected authorization rejection",
        "PASS",
        call_success=False,
        implementation_after=baseline["implementation_before"],
        return_data=baseline["expected_revert"],
    )

    add(
        "Invalid candidate on rejection",
        "UNKNOWN",
        call_success=False,
        implementation_after=baseline["implementation_before"],
        return_data=baseline["expected_revert"],
        candidate_valid_at_observation=False,
    )

    add(
        "Unexpected rejection",
        "UNKNOWN",
        call_success=False,
        implementation_after=baseline["implementation_before"],
        return_data="0x",
    )

    for name, expected, data in cases:
        actual = evaluate(data)

        if actual != expected:
            raise AssertionError(
                f"{name}: expected {expected}, got {actual}"
            )

        print(f"PASS | {name}: {actual}")

    print(f"Policy replay self-tests PASSED: {len(cases)}/{len(cases)}")


def unique_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value

    return result


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        self_test_mode = True
        path = Path(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] != "--self-test":
        self_test_mode = False
        path = Path(sys.argv[1])
    else:
        raise ValueError(
            "Usage: replay_policy.py witness.json | --self-test witness.json"
        )

    with path.open(encoding="utf-8") as f:
        data = json.load(f, object_pairs_hook=unique_keys)

    if not isinstance(data, dict):
        raise ValueError("Witness must be a JSON object")

    if self_test_mode:
        self_test(data)
        return

    recomputed = evaluate(data)
    claimed = data.get("result")

    print(f"Stored verdict: {claimed}")
    print(f"Replay verdict: {recomputed}")

    if recomputed != claimed:
        raise SystemExit("FAIL | Policy replay mismatch")

    print("PASS | Policy verdict reproduced from JSON")
    print("Scope: classification only; no EVM execution attestation")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as exc:
        raise SystemExit(f"ERROR | {exc}")
