#!/usr/bin/env python3
"""Validate the required Adapter8004 Foundry fork-test results."""

import json
import sys
from pathlib import Path

SUITE_SUFFIX = ":Adapter8004MainnetForkTest"

REQUIRED_TESTS = frozenset({
    "testFork_NonOwnerCannotUpgrade()",
    "testFork_OwnerUpgradeDetectedAndRestored()",
    "testFork_HistoricalOwnerCanActuallyUpgrade()",
    "testFork_OutsiderAuthorityRegressionPassFailPass()",
})


class ForkResultError(ValueError):
    pass


def _reject_duplicate_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ForkResultError(f"Duplicate JSON key: {key}")
        result[key] = value

    return result


def load_results(path):
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(
                handle,
                object_pairs_hook=_reject_duplicate_keys,
            )
    except (OSError, json.JSONDecodeError) as exc:
        raise ForkResultError(
            f"Invalid Forge JSON: {exc}"
        ) from exc


def validate_results(data):
    if not isinstance(data, dict):
        raise ForkResultError("Expected JSON object")

    matching = [
        value
        for name, value in data.items()
        if name.endswith(SUITE_SUFFIX)
    ]

    if len(matching) != 1:
        raise ForkResultError(
            "Fork suite was not executed exactly once"
        )

    suite = matching[0]

    if not isinstance(suite, dict):
        raise ForkResultError("Invalid fork suite structure")

    results = suite.get("test_results")

    if not isinstance(results, dict):
        raise ForkResultError("Invalid test_results structure")

    if not results:
        raise ForkResultError("No fork tests executed")

    for name in sorted(REQUIRED_TESTS):
        result = results.get(name)

        status = (
            result.get("status")
            if isinstance(result, dict)
            else None
        )

        if status != "Success":
            raise ForkResultError(
                f"Required fork test {name}: {status}"
            )

    for name, result in results.items():
        if not isinstance(result, dict):
            raise ForkResultError(
                f"Invalid result for {name}"
            )

        if result.get("status") != "Success":
            raise ForkResultError(
                f"Additional fork test {name}: "
                f"{result.get('status')}"
            )

    return {
        name: results[name]["status"]
        for name in sorted(REQUIRED_TESTS)
    }


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: verify_fork_results.py <forge-results.json>",
            file=sys.stderr,
        )
        return 2

    try:
        data = load_results(sys.argv[1])
        statuses = validate_results(data)
    except ForkResultError as exc:
        print(f"ERROR | {exc}", file=sys.stderr)
        return 1

    for name in statuses:
        print(f"PASS | {name}")

    print(
        f"PASS | {len(statuses)} required fork tests executed"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
