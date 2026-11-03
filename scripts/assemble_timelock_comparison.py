#!/usr/bin/env python3
"""Lossless conversion of real Timelock capture to Evidence 1.0.

Structural conversion only. No classification or authentication.
"""

import argparse
import hashlib
import json
import re
import subprocess
import tomllib
import uuid
from pathlib import Path

from validate_comparison_schema import (
    load_document,
    load_schema,
    validate_document,
)

ROOT = Path(__file__).resolve().parents[1]

REGISTRY = json.loads(
    (ROOT / "evidence/semantics/registry.json").read_text()
)

ROUTE = REGISTRY["routes"]["OZ_TIMELOCK_SINGLE"]

SCHEMA = load_schema()

OBS_FIELDS = tuple(
    SCHEMA["$defs"]["routedObservation"]["properties"]
)

assert len(OBS_FIELDS) == 32

SPEC_FIELDS = {
    "timelock": "timelock",
    "proposer": "proposer",
    "executor": "executor",
    "proxyAdmin": "proxy_admin",
    "proxy": "proxy",
    "candidate": "candidate",
    "predecessor": "predecessor",
    "salt": "salt",
    "property": "property",
}

SOURCE_INPUTS = (
    "foundry.toml",
    "src/AuthorityProbe.sol",
    "src/ComparativeAuthorityProbe.sol",
    "src/TimelockAuthorityProbe.sol",
    "test/TimelockAuthorityIntegration.t.sol",
    "test/TimelockComparisonEvidenceCapture.t.sol",
    "scripts/assemble_timelock_comparison.py",
    "scripts/replay_timelock_comparison.py",
    "scripts/test_timelock_comparison_mutations.py",
    "scripts/run_timelock_comparison.py",
    "scripts/build_provenance.py",
    "scripts/replay_build_compilation.py",
    "scripts/validate_comparison_schema.py",
    "evidence/semantics/registry.json",
    "evidence/schema/comparison-1.0.schema.json",
)


def git(*args, cwd=ROOT):
    return subprocess.check_output(
        ["git", *args],
        cwd=cwd,
        text=True,
    ).strip()


def source_inputs():
    result = []

    for name in SOURCE_INPUTS:
        data = (ROOT / name).read_bytes()

        result.append({
            "path": name,
            "sha256": hashlib.sha256(data).hexdigest(),
        })

    return result


def expected_capture_keys():
    keys = {
        "format",
        "chain_id",
        "scenario_id",
        "inner_calldata",
        "outer_calldata",
        "operation_id",
        "comparison_scenario_key",
        "comparison_verdict",
        "comparison_reason",
    }

    keys.update(SPEC_FIELDS.values())

    for stage in ("before", "after"):
        keys.update(
            f"{stage}_{field}"
            for field in OBS_FIELDS
        )

        keys.update({
            f"{stage}_expectedActiveImplementation",
            f"{stage}_status",
            f"{stage}_reason",
        })

    return keys


def assemble(capture, run_id=None):
    if capture.get("format") != (
        "protocol-sentinel-routed-capture-v1"
    ):
        raise ValueError("Invalid routed capture format")

    expected = expected_capture_keys()
    actual = set(capture)

    if actual != expected:
        raise ValueError(
            "Raw capture field mismatch: "
            f"missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )

    if run_id is None:
        run_id = uuid.uuid4().hex

    if re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
        raise ValueError("Invalid run ID")

    waiting = (
        capture["property"] == "NOT_READY_EXECUTION_REJECTED"
    )

    if capture["property"] not in (
        "READY_UPGRADE_SUCCEEDS",
        "NOT_READY_EXECUTION_REJECTED",
    ):
        raise ValueError("Unsupported Timelock property")

    stages = {}

    for name in ("before", "after"):
        # Read every observed field from the original raw capture.
        # Never regenerate an observed value from the scenario.
        obs = {
            field: capture[f"{name}_{field}"]
            for field in OBS_FIELDS
        }

        stages[name] = {
            "expectedActiveImplementation":
                capture[f"{name}_expectedActiveImplementation"],
            "observation": obs,
            "evaluation": {
                "status": capture[f"{name}_status"],
                "reason": capture[f"{name}_reason"],
            },
        }

    config = tomllib.loads(
        (ROOT / "foundry.toml").read_text()
    )

    deps = {
        "openzeppelinContracts": git(
            "rev-parse",
            "HEAD",
            cwd=ROOT / "lib/openzeppelin-contracts",
        ),
        "openzeppelinContractsUpgradeable": git(
            "rev-parse",
            "HEAD",
            cwd=ROOT / "lib/openzeppelin-contracts-upgradeable",
        ),
    }

    doc = {
        "format": REGISTRY["format"],
        "schema_version": REGISTRY["schemaVersion"],
        "route": "OZ_TIMELOCK_SINGLE",
        "semantics_version": ROUTE["semanticsVersion"],
        "scenario": {
            "scenarioId": capture["scenario_id"],
            "spec": {
                name: capture[raw_name]
                for name, raw_name in SPEC_FIELDS.items()
            },
            "derived": {
                "innerCalldata": capture["inner_calldata"],
                "outerCalldata": capture["outer_calldata"],
                "operationId": capture["operation_id"],
            },
        },
        "stages": stages,
        "comparison": {
            "scenarioKey":
                capture["comparison_scenario_key"],
            "verdict":
                capture["comparison_verdict"],
            "reason":
                capture["comparison_reason"],
        },
        "environment": {
            "fixtureId": (
                "oz-timelock-transparent-v1-v2-waiting"
                if waiting else
                "oz-timelock-transparent-v1-v2-ready"
            ),
            "executionMode": "local_fixture",
            "chainId": capture["chain_id"],
            "forgeVersion": subprocess.check_output(
                ["forge", "--version"],
                text=True,
            ).strip().splitlines()[0],
            "solcVersion":
                config["profile"]["default"]["solc_version"],
            "dependencyRevisions": deps,
        },
        "provenance": {
            "repository":
                "NothernZhongKui/protocol-sentinel",
            "sourceCommit": git("rev-parse", "HEAD"),
            "workingTreeClean":
                not bool(git("status", "--porcelain")),
            "runId": run_id,
            "sourceInputs": source_inputs(),
            "reproduceCommand": (
                "python3.12 scripts/run_timelock_comparison.py"
            ),
        },
    }

    validate_document(doc, SCHEMA)

    return doc


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-id")

    args = parser.parse_args()

    capture = load_document(args.capture)

    doc = assemble(capture, args.run_id)

    if args.output:
        output = args.output
    else:
        output = (
            ROOT / "artifacts/demo"
            / f"timelock-comparison-provisional-{uuid.uuid4().hex}.json"
        )

    if not output.is_absolute():
        output = ROOT / output

    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("x", encoding="utf-8") as file:
        json.dump(
            doc,
            file,
            indent=2,
            sort_keys=True,
        )
        file.write("\n")

    print(output)


if __name__ == "__main__":
    main()
