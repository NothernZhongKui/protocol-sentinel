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


class SchemaError(ValueError):
    """Invalid or unsupported evidence schema."""


def validate_schema(data, *, allow_legacy=False):
    if not isinstance(data, dict):
        raise SchemaError("Witness must be a JSON object")

    version = data.get("schema_version")

    if type(version) is not str or version not in ("0.2", "0.3", "0.4"):
        raise SchemaError("Unsupported schema version")

    if version != "0.4" and not allow_legacy:
        raise SchemaError("Legacy schema requires --allow-legacy")

    if version in ("0.2", "0.3"):
        if "target_valid_at_observation" in data:
            raise SchemaError(
                "Target validity field incompatible with legacy schema"
            )

    if version == "0.2" and "reason" in data:
        raise SchemaError("Reason field incompatible with schema 0.2")

    if version in ("0.3", "0.4") and "reason" not in data:
        raise SchemaError("Policy reason missing")

    if version == "0.4" and "target_valid_at_observation" not in data:
        raise SchemaError("Target validity missing")

    return version


def evaluate_detailed(data, *, allow_legacy=False):
    version = validate_schema(data, allow_legacy=allow_legacy)
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

    # Older schemas did not capture this precondition.
    # Preserve historical classification, not proof of target validity.
    if version == "0.4":
        target_valid = flag(data, "target_valid_at_observation")
    else:
        target_valid = True

    if slot != ERC1967_SLOT:
        return "UNKNOWN", "INVALID_SLOT"

    if (
        actor != expected_actor
        or origin != expected_actor
        or target != expected_target
    ):
        return "UNKNOWN", "CONTEXT_MISMATCH"

    if not target_valid:
        return "UNKNOWN", "INVALID_TARGET"

    canonical = (
        UPGRADE_SELECTOR
        + candidate.to_bytes(32, "big")
        + (64).to_bytes(32, "big")
        + (0).to_bytes(32, "big")
    )

    if calldata != canonical:
        return "UNKNOWN", "NON_CANONICAL_CALLDATA"

    unchanged = before == after

    if not success:
        if not candidate_valid:
            return "UNKNOWN", "INVALID_CANDIDATE"

        if unchanged and expected_revert and return_data == expected_revert:
            return "PASS", "NONE"

        return "UNKNOWN", "UNEXPECTED_REVERT"

    if policy == "NO_SUCCESSFUL_UPGRADE_CALL":
        return "FAIL", "NONE"

    if not unchanged:
        return "FAIL", "NONE"

    return "UNKNOWN", "SUCCESS_WITHOUT_REPLACEMENT"


def evaluate(data, *, allow_legacy=False):
    # Backward-compatible status-only return type.
    return evaluate_detailed(data, allow_legacy=allow_legacy)[0]


def self_test(baseline):
    cases = []

    def add(name, expected, **changes):
        data = dict(baseline)
        data.update(changes)
        cases.append((name, expected, data))

    add("Original exported FAIL", "FAIL")
    add(
        "Invalid target precondition",
        "UNKNOWN",
        target_valid_at_observation=False,
    )

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
        "Empty expected revert cannot prove authorization",
        "UNKNOWN",
        call_success=False,
        implementation_after=baseline["implementation_before"],
        expected_revert="0x",
        return_data="0x",
        candidate_valid_at_observation=True,
    )

    add(
        "Unexpected rejection",
        "UNKNOWN",
        call_success=False,
        implementation_after=baseline["implementation_before"],
        return_data="0x",
    )

    expected_reasons = {
        "Original exported FAIL": "NONE",
        "Invalid target precondition": "INVALID_TARGET",
        "P1: candidate precedence": "NONE",
        "Origin mismatch": "CONTEXT_MISMATCH",
        "Target mismatch": "CONTEXT_MISMATCH",
        "Incorrect implementation slot": "INVALID_SLOT",
        "Unrelated calldata": "NON_CANONICAL_CALLDATA",
        "P2: high bits, replacement policy": "SUCCESS_WITHOUT_REPLACEMENT",
        "P2: high bits, successful-call policy": "NONE",
        "Expected authorization rejection": "NONE",
        "Invalid candidate on rejection": "INVALID_CANDIDATE",
        "Empty expected revert cannot prove authorization": "UNEXPECTED_REVERT",
        "Unexpected rejection": "UNEXPECTED_REVERT",
    }

    for name, expected, data in cases:
        actual, reason = evaluate_detailed(data)

        if reason != expected_reasons[name]:
            raise AssertionError(
                f"{name}: expected reason {expected_reasons[name]}, "
                f"got {reason}"
            )

        if actual != expected:
            raise AssertionError(
                f"{name}: expected {expected}, got {actual}"
            )

        print(f"PASS | {name}: {actual} / {reason}")

    print(f"Policy replay self-tests PASSED: {len(cases)}/{len(cases)}")


def unique_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value

    return result


def main():
    self_test_mode = False
    allow_legacy = False

    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        self_test_mode = True
        path = Path(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--allow-legacy":
        allow_legacy = True
        path = Path(sys.argv[2])
    elif len(sys.argv) == 2 and not sys.argv[1].startswith("--"):
        path = Path(sys.argv[1])
    else:
        raise ValueError(
            "Usage: replay_policy.py witness.json | "
            "--allow-legacy witness.json | --self-test witness.json"
        )

    with path.open(encoding="utf-8") as f:
        data = json.load(f, object_pairs_hook=unique_keys)

    if not isinstance(data, dict):
        raise ValueError("Witness must be a JSON object")

    version = validate_schema(data, allow_legacy=allow_legacy)

    if self_test_mode:
        self_test(data)
        return

    if version != "0.4":
        print(
            f"LEGACY | Schema {version}: target validation unavailable"
        )

    recomputed, recomputed_reason = evaluate_detailed(
        data, allow_legacy=allow_legacy
    )
    claimed = data.get("result")

    print(f"Stored verdict: {claimed}")
    print(f"Replay verdict: {recomputed}")

    if recomputed != claimed:
        raise SystemExit("FAIL | Policy replay mismatch")

    # Legacy witnesses without reason remain valid.
    # New witnesses must match independently computed diagnostics.
    if "reason" in data:
        claimed_reason = data["reason"]

        print(f"Stored reason: {claimed_reason}")
        print(f"Replay reason: {recomputed_reason}")

        if (
            not isinstance(claimed_reason, str)
            or claimed_reason != recomputed_reason
        ):
            raise SystemExit("FAIL | Policy reason mismatch")

    print("PASS | Policy verdict reproduced from JSON")
    print("Scope: classification only; no EVM execution attestation")


if __name__ == "__main__":
    try:
        main()
    except SchemaError as exc:
        raise SystemExit(f"FAIL | {exc}")
    except (ValueError, KeyError, OSError) as exc:
        raise SystemExit(f"ERROR | {exc}")
