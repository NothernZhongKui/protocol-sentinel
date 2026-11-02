#!/usr/bin/env python3
"""Check legacy classification compatibility and format isolation."""

import argparse
import copy
import json
from pathlib import Path

from replay_policy import evaluate_detailed, validate_schema, SchemaError
from validate_comparison_schema import (
    EvidenceSchemaError, load_document, validate_document,
)

CASES = ("baseline", "risky", "self-replacement", "self-call", "fixed")
OUTPUT = Path("artifacts/demo")


def rejected(fn):
    try:
        fn()
    except (SchemaError, EvidenceSchemaError):
        return
    raise AssertionError("Invalid cross-format input accepted")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", type=Path, required=True)
    parser.add_argument("--timelock", type=Path, required=True)
    args = parser.parse_args()

    checked = 0
    opt_in = 0

    for name in CASES:
        current = json.loads(
            (OUTPUT / f"policy-replay-{name}.json").read_text()
        )

        assert current["schema_version"] == "0.4"
        assert current["target_valid_at_observation"] is True

        expected = (current["result"], current["reason"])

        for version in ("0.2", "0.3", "0.4"):
            witness = copy.deepcopy(current)
            witness["schema_version"] = version

            if version != "0.4":
                witness.pop("target_valid_at_observation")

            if version == "0.2":
                witness.pop("reason")

            allow_legacy = version != "0.4"

            assert evaluate_detailed(
                witness, allow_legacy=allow_legacy
            ) == expected, (name, version)

            checked += 1

            if allow_legacy:
                rejected(lambda w=witness: validate_schema(w))
                opt_in += 1

    for path, route in (
        (args.direct, "DIRECT_EOA_UUPS"),
        (args.timelock, "OZ_TIMELOCK_SINGLE"),
    ):
        comparison = load_document(path)

        assert comparison["route"] == route
        assert validate_document(comparison)

        rejected(
            lambda d=comparison: validate_schema(
                d, allow_legacy=True
            )
        )

        rejected(
            lambda: validate_document(
                json.loads(
                    (OUTPUT / "policy-replay-baseline.json").read_text()
                )
            )
        )

    assert checked == 15
    assert opt_in == 10

    # Legacy-shaped cases are derived from fresh 0.4 observations.
    # They are not claimed to be archived historical captures.
    print("PASS | Legacy classification parity: 15/15")
    print("PASS | Explicit legacy opt-in: 10/10")
    print("PASS | Comparison/legacy format isolation")
    print("LEGACY COMPATIBILITY: PASS")


if __name__ == "__main__":
    main()
