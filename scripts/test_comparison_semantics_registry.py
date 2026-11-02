#!/usr/bin/env python3
"""Validate frozen comparison semantics against Solidity sources."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "evidence/semantics/registry.json"

SOURCE_PATHS = (
    "src/AuthorityProbe.sol",
    "src/ComparativeAuthorityProbe.sol",
    "src/TimelockAuthorityProbe.sol",
)

OZ_TIMELOCK = (
    "lib/openzeppelin-contracts/contracts/"
    "governance/TimelockController.sol"
)

EXPECTED_ROUTES = {
    "DIRECT_EOA_UUPS": "direct-eoa-v1",
    "OZ_TIMELOCK_SINGLE": "oz-timelock-single-v1",
}


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    print(f"PASS | {description}")


def extract_enum(source, name):
    match = re.search(
        r"\benum\s+" + re.escape(name) + r"\s*\{([^}]+)\}",
        source,
    )
    if match is None:
        raise AssertionError(f"Missing Solidity enum: {name}")

    values = []
    for entry in match.group(1).split(","):
        entry = entry.strip()
        if entry:
            values.append(entry)

    return values


def main():
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))

    check(
        data["format"] == "protocol-sentinel-comparison",
        "Comparison format identifier"
    )

    check(
        data["schemaVersion"] == "1.0",
        "Independent schema version"
    )

    check(
        {
            name: route["semanticsVersion"]
            for name, route in data["routes"].items()
        } == EXPECTED_ROUTES,
        "Exact supported route/semantics pairs"
    )

    reference = data["referenceCommit"]

    check(
        re.fullmatch(r"[0-9a-f]{40}", reference) is not None,
        "Full reference commit SHA"
    )

    sources = {}

    for path in SOURCE_PATHS:
        current = (ROOT / path).read_bytes()

        original = subprocess.check_output(
            ["git", "show", f"{reference}:{path}"],
            cwd=ROOT,
        )

        check(
            current == original,
            f"Frozen reference source: {path}"
        )

        sources[path] = current.decode("utf-8")

    oz_source = (ROOT / OZ_TIMELOCK).read_text(
        encoding="utf-8"
    )

    for route_name, route in data["routes"].items():
        combined = "\n".join(
            sources[path] for path in route["sourceFiles"]
        )

        for field in (
            "evaluator",
            "comparator",
            "scenarioKeyFunction",
        ):
            function_name = route[field]

            check(
                re.search(
                    r"\bfunction\s+"
                    + re.escape(function_name)
                    + r"\s*\(",
                    combined,
                ) is not None,
                f"{route_name}: {function_name}"
            )

        domain = route["comparisonDomain"]

        check(
            domain in combined,
            f"{route_name}: comparison domain"
        )

        for enum_name, expected in route["enums"].items():
            source = (
                oz_source if enum_name == "OperationState"
                else combined
            )

            actual = extract_enum(source, enum_name)

            check(
                actual == expected,
                f"{route_name}: {enum_name} ordinals"
            )

    direct = data["routes"]["DIRECT_EOA_UUPS"]

    check(
        len(direct["scenarioKeyAbiTypes"]) == 9,
        "Direct scenario key ABI arity"
    )

    routed = data["routes"]["OZ_TIMELOCK_SINGLE"]

    check(
        len(routed["operationIdAbiTypes"]) == 5,
        "Timelock operation ID ABI arity"
    )

    check(
        len(routed["scenarioKeyAbiTypes"]) == 6,
        "Timelock scenario key ABI arity"
    )

    check(
        "TIMELOCK_COMPARISON_DOMAIN" in
        sources["src/TimelockAuthorityProbe.sol"],
        "Separate Timelock comparison domain"
    )

    print()
    print("SEMANTICS REGISTRY: PASS")
    print("Reference:", reference)
    print("Routes:", len(EXPECTED_ROUTES))
    print(
        "Scope: source and enum consistency; "
        "ABI golden vectors are the next milestone."
    )


if __name__ == "__main__":
    main()
