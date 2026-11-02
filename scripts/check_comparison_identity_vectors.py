#!/usr/bin/env python3
"""Reproduce frozen Solidity identity vectors using Python ABI/Keccak."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from eth_abi import encode
from eth_hash.auto import keccak

ROOT = Path(__file__).resolve().parents[1]

REGISTRY = ROOT / "evidence/semantics/registry.json"
GOLDEN = ROOT / "evidence/vectors/comparison-identity-v1.json"
GENERATED = ROOT / "artifacts/demo/comparison-abi-vectors.json"

ERC1967_IMPL_SLOT = bytes.fromhex(
    "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
)

DIRECT_LENGTHS = (0, 1, 31, 32, 33)


def unique_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate vector field: {key}")
        result[key] = value

    return result


def invalid_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def strict_json(source):
    return json.loads(
        source,
        object_pairs_hook=unique_keys,
        parse_constant=invalid_constant,
    )


def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print(f"PASS | {label}", flush=True)


def hexbytes(value, size=None):
    if (
        not isinstance(value, str)
        or re.fullmatch(r"0x(?:[0-9a-fA-F]{2})*", value) is None
    ):
        raise AssertionError(f"Invalid hexadecimal value: {value}")

    raw = bytes.fromhex(value[2:])

    if size is not None and len(raw) != size:
        raise AssertionError(f"Wrong byte length: {value}")

    return raw


def address(value):
    return hexbytes(value, 20)


def expected_hex(actual, expected, label):
    check(
        hexbytes(actual) == expected,
        label
    )


def selector(signature):
    return keccak(signature.encode("ascii"))[:4]


def abi_hash(types, values):
    return keccak(encode(types, values))


def generate_from_solidity():
    GENERATED.parent.mkdir(parents=True, exist_ok=True)
    GENERATED.unlink(missing_ok=True)

    env = os.environ.copy()
    env["EXPORT_COMPARISON_VECTORS"] = "true"

    command = [
        "forge", "test",
        "--json",
        "--threads", "1",
        "--match-contract", "ComparisonEvidenceVectorsTest",
        "--match-test", "test_ExportComparisonIdentityVectors",
    ]

    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    try:
        results = strict_json(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "Forge did not return valid JSON:\n"
            + result.stderr[-2000:]
            + "\n"
            + result.stdout[-2000:]
        ) from exc

    matches = []

    for suite_name, suite in results.items():
        if not suite_name.endswith(
            ":ComparisonEvidenceVectorsTest"
        ):
            continue

        for test_name, test_result in suite.get(
            "test_results", {}
        ).items():
            if test_name == "test_ExportComparisonIdentityVectors()":
                matches.append(test_result.get("status"))

    check(
        result.returncode == 0
        and matches == ["Success"],
        f"Foundry required producer executed: {matches}"
    )

    check(
        GENERATED.is_file(),
        "Fresh identity vectors generated"
    )

    return strict_json(GENERATED.read_text(encoding="utf-8"))


def verify_direct(data, registry):
    route = registry["routes"]["DIRECT_EOA_UUPS"]

    domain = keccak(route["comparisonDomain"].encode())

    scenario_id = hexbytes(data["direct_scenario_id"], 32)
    actor = address(data["direct_actor"])
    target = address(data["direct_target"])
    candidate = address(data["direct_candidate"])

    calldata = selector(route["callSignature"]) + encode(
        ["address", "bytes"],
        [candidate, b""]
    )

    expected_hex(
        data["direct_calldata"],
        calldata,
        "Direct canonical calldata"
    )

    policies = route["enums"]["UpgradePolicy"]
    check(len(policies) == 2, "Direct enum mapping")

    for policy in range(len(policies)):
        for length in DIRECT_LENGTHS:
            suffix = f"{policy}_{length}"

            return_data = hexbytes(
                data[f"direct_revert_{suffix}"]
            )

            check(
                return_data == bytes(range(1, length + 1)),
                f"Expected revert payload: {suffix}"
            )

            digest = abi_hash(
                route["scenarioKeyAbiTypes"],
                [
                    domain,
                    scenario_id,
                    actor,
                    target,
                    candidate,
                    calldata,
                    return_data,
                    policy,
                    ERC1967_IMPL_SLOT,
                ]
            )

            expected_hex(
                data[f"direct_key_{suffix}"],
                digest,
                f"Direct scenario key: {suffix}"
            )


def verify_routed(data, registry):
    route = registry["routes"]["OZ_TIMELOCK_SINGLE"]

    domain = keccak(route["comparisonDomain"].encode())

    scenario_id = hexbytes(data["routed_scenario_id"], 32)
    timelock = address(data["routed_timelock"])
    proposer = address(data["routed_proposer"])
    executor = address(data["routed_executor"])
    proxy_admin = address(data["routed_proxy_admin"])
    proxy = address(data["routed_proxy"])
    candidate = address(data["routed_candidate"])
    salt = hexbytes(data["routed_salt"], 32)

    inner = selector(route["innerCallSignature"]) + encode(
        ["address", "address", "bytes"],
        [proxy, candidate, b""]
    )

    for index in range(2):
        property_ordinal = data[f"routed_property_{index}"]

        check(
            type(property_ordinal) is int
            and property_ordinal == index,
            f"Timelock property enum ordinal: {index}"
        )

        predecessor = hexbytes(
            data[f"routed_predecessor_{index}"],
            32
        )

        check(
            predecessor == (
                bytes(32) if index == 0
                else (0x5050).to_bytes(32, "big")
            ),
            f"Timelock predecessor fixture: {index}"
        )

        expected_hex(
            data[f"routed_inner_{index}"],
            inner,
            f"Timelock inner calldata: {index}"
        )

        operation_id = abi_hash(
            route["operationIdAbiTypes"],
            [
                proxy_admin,
                0,
                inner,
                predecessor,
                salt,
            ],
        )

        expected_hex(
            data[f"routed_operation_id_{index}"],
            operation_id,
            f"Timelock operation ID: {index}"
        )

        outer = selector(route["outerCallSignature"]) + encode(
            ["address", "uint256", "bytes", "bytes32", "bytes32"],
            [
                proxy_admin,
                0,
                inner,
                predecessor,
                salt,
            ]
        )

        expected_hex(
            data[f"routed_outer_{index}"],
            outer,
            f"Timelock outer calldata: {index}"
        )

        scenario_tuple = (
            timelock,
            proposer,
            executor,
            proxy_admin,
            proxy,
            candidate,
            predecessor,
            salt,
            property_ordinal,
        )

        scenario_key = abi_hash(
            route["scenarioKeyAbiTypes"],
            [
                domain,
                scenario_id,
                scenario_tuple,
                operation_id,
                outer,
                ERC1967_IMPL_SLOT,
            ],
        )

        expected_hex(
            data[f"routed_scenario_key_{index}"],
            scenario_key,
            f"Timelock scenario key: {index}"
        )


def verify_all(data):
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    check(
        data["format"] == "protocol-sentinel-identity-v1",
        "Golden vector format"
    )

    # NIST SHA3 and Ethereum Keccak must never be interchanged.
    message = b"protocol-sentinel-keccak-control"

    check(
        hashlib.sha3_256(message).digest() != keccak(message),
        "Ethereum Keccak differs from NIST SHA3-256"
    )

    expected_keys = {
        "format",
        "direct_scenario_id",
        "direct_actor",
        "direct_target",
        "direct_candidate",
        "direct_calldata",
        "routed_scenario_id",
        "routed_timelock",
        "routed_proposer",
        "routed_executor",
        "routed_proxy_admin",
        "routed_proxy",
        "routed_candidate",
        "routed_salt",
    }

    for policy in range(2):
        for length in DIRECT_LENGTHS:
            suffix = f"{policy}_{length}"
            expected_keys.add(f"direct_revert_{suffix}")
            expected_keys.add(f"direct_key_{suffix}")

    for index in range(2):
        for prefix in (
            "routed_property_",
            "routed_predecessor_",
            "routed_inner_",
            "routed_outer_",
            "routed_operation_id_",
            "routed_scenario_key_",
        ):
            expected_keys.add(f"{prefix}{index}")

    check(
        set(data) == expected_keys,
        "Exact frozen vector field set"
    )

    verify_direct(data, registry)
    verify_routed(data, registry)

    print()
    print("PASS | Independent Solidity/Python identity equivalence")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")

    args = parser.parse_args()

    fresh = generate_from_solidity()

    # Both modes require independent Python recomputation.
    verify_all(fresh)

    canonical = json.dumps(
        fresh,
        indent=2,
        sort_keys=True,
    ) + "\n"

    if args.write:
        if GOLDEN.exists():
            raise AssertionError(
                "Golden vector file already exists; refusing overwrite"
            )

        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(canonical, encoding="utf-8")

        print("WRITE |", GOLDEN.relative_to(ROOT))
    else:
        check(
            GOLDEN.is_file(),
            "Committed golden vectors exist"
        )

        check(
            GOLDEN.read_text(encoding="utf-8") == canonical,
            "Fresh Solidity results match frozen golden vectors"
        )

        verify_all(strict_json(GOLDEN.read_text()))

    print()
    print("COMPARISON IDENTITY GOLDEN VECTORS: PASS")


if __name__ == "__main__":
    main()
