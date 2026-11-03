#!/usr/bin/env python3
"""Lossless mapping of real Foundry capture into provisional schema 1.0.

This is not a classifier and cannot certify execution.
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
    validate_document,
)

ROOT = Path(__file__).resolve().parents[1]

REGISTRY = json.loads(
    (ROOT / "evidence/semantics/registry.json").read_text()
)

ROUTE = REGISTRY["routes"]["DIRECT_EOA_UUPS"]

FIELDS = (
    "actor",
    "txOrigin",
    "target",
    "success",
    "returnData",
    "observedSlot",
    "implementationBefore",
    "implementationAfter",
    "callData",
    "candidateValidAtObservation",
    "targetValidAtObservation",
)

SOURCE_INPUTS = (
    "foundry.toml",
    "src/AuthorityProbe.sol",
    "src/ComparativeAuthorityProbe.sol",
    "test/DirectComparisonEvidenceCapture.t.sol",
    "test/fixtures/RoleVaultVersions.sol",
    "evidence/semantics/registry.json",
    "evidence/schema/comparison-1.0.schema.json",
    "scripts/assemble_direct_comparison.py",
    "scripts/replay_direct_comparison.py",
    "scripts/validate_comparison_schema.py",
    "scripts/run_direct_comparison.py",
    "scripts/build_provenance.py",
    "scripts/replay_build_compilation.py",
)


def git(*args, cwd=ROOT):
    return subprocess.check_output(
        ["git", *args],
        cwd=cwd,
        text=True,
    ).strip()


def source_inputs():
    entries = []

    for name in SOURCE_INPUTS:
        content = (ROOT / name).read_bytes()

        entries.append({
            "path": name,
            "sha256": hashlib.sha256(content).hexdigest(),
        })

    return entries


def assemble(capture, run_id=None, *, context=None):
    expected = {
        "format",
        "chain_id",
        "scenario_id",
        "actor",
        "target",
        "candidate",
        "expected_revert",
        "policy",
        "canonical_calldata",
        "comparison_scenario_key",
        "comparison_verdict",
        "comparison_reason",
    }

    for stage in ("before", "after"):
        expected.update(
            f"{stage}_{name}" for name in FIELDS
        )
        expected.update({
            f"{stage}_expectedActiveImplementation",
            f"{stage}_status",
            f"{stage}_reason",
        })

    if set(capture) != expected:
        raise ValueError(
            f"Unexpected capture fields: "
            f"missing={sorted(expected - set(capture))}, "
            f"extra={sorted(set(capture) - expected)}"
        )

    if capture["format"] != "protocol-sentinel-direct-capture-v1":
        raise ValueError("Unexpected raw capture format")

    stages = {}

    for name in ("before", "after"):
        # Preserve the original Solidity observations exactly.
        observation = {
            field: capture[f"{name}_{field}"]
            for field in FIELDS
        }

        stages[name] = {
            "expectedActiveImplementation":
                capture[f"{name}_expectedActiveImplementation"],
            "observation": observation,
            "evaluation": {
                "status": capture[f"{name}_status"],
                "reason": capture[f"{name}_reason"],
            },
        }

    if context is None:
        # Preserve the existing v0.4.1 demonstration contract.
        project_root = ROOT
        fixture_id = "role-vault-v1-to-risky-v2"
        repository = "NothernZhongKui/protocol-sentinel"
        manifest_inputs = source_inputs()
        reproduce_command = (
            "python3.12 scripts/run_direct_comparison.py"
        )
    else:
        required = {
            "projectRoot",
            "fixtureId",
            "repository",
            "sourceInputs",
            "reproduceCommand",
        }

        if not isinstance(context, dict) or set(context) != required:
            raise ValueError("Invalid external assembly context")

        project_root = Path(context["projectRoot"]).resolve()

        if not (project_root / "foundry.toml").is_file():
            raise ValueError("Missing consumer Foundry configuration")

        fixture_id = context["fixtureId"]
        repository = context["repository"]
        manifest_inputs = context["sourceInputs"]
        reproduce_command = context["reproduceCommand"]

        for label, value in (
            ("fixtureId", fixture_id),
            ("repository", repository),
            ("reproduceCommand", reproduce_command),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Invalid {label}")

        if not isinstance(manifest_inputs, list) or not manifest_inputs:
            raise ValueError("Missing consumer source inputs")

        seen = set()

        for item in manifest_inputs:
            if not isinstance(item, dict) or set(item) != {
                "path", "sha256"
            }:
                raise ValueError("Invalid source input entry")

            name = item["path"]
            digest = item["sha256"]

            if not isinstance(name, str) or not isinstance(digest, str):
                raise ValueError("Invalid source input types")

            relative = Path(name)

            if (
                relative.is_absolute()
                or ".." in relative.parts
                or name in seen
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                raise ValueError("Unsafe or duplicate source input")

            seen.add(name)

            local = (project_root / relative).resolve()

            if (
                not local.is_relative_to(project_root)
                or not local.is_file()
            ):
                raise ValueError(f"Missing source: {name}")

            actual = hashlib.sha256(local.read_bytes()).hexdigest()

            if actual != digest:
                raise ValueError(f"Source hash mismatch: {name}")

    config = tomllib.loads(
        (project_root / "foundry.toml").read_text()
    )

    deps = {}

    for name, directory in (
        ("openzeppelinContracts", "lib/openzeppelin-contracts"),
        (
            "openzeppelinContractsUpgradeable",
            "lib/openzeppelin-contracts-upgradeable",
        ),
    ):
        dependency = project_root / directory

        if not dependency.is_dir():
            raise ValueError(f"Missing dependency: {directory}")

        revision = git("rev-parse", "HEAD", cwd=dependency)

        index = git(
            "ls-files", "--stage", "--", directory,
            cwd=project_root,
        ).split()

        if (
            len(index) != 4
            or index[0] != "160000"
            or index[1] != revision
            or index[3] != directory
        ):
            raise ValueError(
                f"Unpinned dependency: {directory}"
            )

        deps[name] = revision

    clean = not bool(
        git("status", "--porcelain", cwd=project_root)
    )

    if run_id is None:
        run_id = uuid.uuid4().hex

    if re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
        raise ValueError("Invalid run identifier")

    doc = {
        "format": REGISTRY["format"],
        "schema_version": REGISTRY["schemaVersion"],
        "route": "DIRECT_EOA_UUPS",
        "semantics_version": ROUTE["semanticsVersion"],
        "scenario": {
            "scenarioId": capture["scenario_id"],
            "spec": {
                "actor": capture["actor"],
                "target": capture["target"],
                "candidate": capture["candidate"],
                "expectedRevert": capture["expected_revert"],
                "policy": capture["policy"],
            },
            "derived": {
                "canonicalCalldata": capture["canonical_calldata"],
            },
        },
        "stages": stages,
        "comparison": {
            "scenarioKey": capture["comparison_scenario_key"],
            "verdict": capture["comparison_verdict"],
            "reason": capture["comparison_reason"],
        },
        "environment": {
            "fixtureId": fixture_id,
            "executionMode": "local_fixture",
            "chainId": capture["chain_id"],
            "forgeVersion": subprocess.check_output(
                ["forge", "--version"], text=True
            ).strip().splitlines()[0],
            "solcVersion": config["profile"]["default"]["solc_version"],
            "dependencyRevisions": deps,
        },
        "provenance": {
            "repository": repository,
            "sourceCommit": git("rev-parse", "HEAD", cwd=project_root),
            "workingTreeClean": clean,
            "runId": run_id,
            "sourceInputs": manifest_inputs,
            "reproduceCommand": reproduce_command,
        },
    }

    validate_document(doc)

    return doc, run_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_capture", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-id")
    args = parser.parse_args()

    capture = load_document(args.raw_capture)

    document, run_id = assemble(capture, args.run_id)

    output = args.output

    if output is None:
        output = ROOT / "artifacts/demo" / (
            f"direct-comparison-provisional-{run_id}.json"
        )

    if not output.is_absolute():
        output = ROOT / output

    output.parent.mkdir(parents=True, exist_ok=True)

    # Never overwrite another run's evidence.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write("\n")

    print(output)


if __name__ == "__main__":
    main()
