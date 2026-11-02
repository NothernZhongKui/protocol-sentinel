#!/usr/bin/env python3
"""Require actual successful execution of every Timelock consumer test."""

import json
import sys
from pathlib import Path

SUITE_SUFFIX = ":SentinelTimelockConsumerTest"

REQUIRED_TESTS = frozenset({
    "test_ConsumerWaitingRejectsEarlyExecution()",
    "test_ConsumerReadyUpgradeAndRestoration()",
    "test_ConsumerComparativeUpgradeRoute()",
})


class ConsumerResultError(ValueError):
    pass


def reject_duplicate_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ConsumerResultError(f"Duplicate JSON key: {key}")
        result[key] = value

    return result


def load_results(path):
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(
                handle,
                object_pairs_hook=reject_duplicate_keys,
            )
    except (OSError, json.JSONDecodeError) as exc:
        raise ConsumerResultError(
            f"Invalid Forge JSON: {exc}"
        ) from exc


def validate_results(data):
    if not isinstance(data, dict):
        raise ConsumerResultError("Expected a JSON object")

    suites = [
        value
        for name, value in data.items()
        if name.endswith(SUITE_SUFFIX)
    ]

    if len(suites) != 1:
        raise ConsumerResultError(
            "Expected exactly one Timelock consumer suite"
        )

    suite = suites[0]

    if not isinstance(suite, dict):
        raise ConsumerResultError("Invalid suite")

    results = suite.get("test_results")

    if not isinstance(results, dict):
        raise ConsumerResultError("Missing test_results")

    if len(results) < len(REQUIRED_TESTS):
        raise ConsumerResultError(
            "Not all required consumer tests executed"
        )

    for name in sorted(REQUIRED_TESTS):
        result = results.get(name)

        status = (
            result.get("status")
            if isinstance(result, dict)
            else None
        )

        if status != "Success":
            raise ConsumerResultError(
                f"Required consumer test {name}: {status}"
            )

    for name, result in results.items():
        status = (
            result.get("status")
            if isinstance(result, dict)
            else None
        )

        if status != "Success":
            raise ConsumerResultError(
                f"Additional consumer test {name}: {status}"
            )

    return sorted(results)


def main():
    if len(sys.argv) != 2:
        print(
            "Usage: verify_timelock_consumer_results.py "
            "<forge-results.json>",
            file=sys.stderr,
        )
        return 2

    try:
        tests = validate_results(load_results(sys.argv[1]))
    except ConsumerResultError as exc:
        print(f"ERROR | {exc}", file=sys.stderr)
        return 1

    for test in tests:
        print(f"PASS | {test}")

    print(
        f"PASS | {len(tests)} consumer tests executed successfully"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
