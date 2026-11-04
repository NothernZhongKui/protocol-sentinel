#!/usr/bin/env python3
"""Lossless Direct capture -> comparison Evidence 1.1 for nested Foundry."""

import re

from assemble_direct_comparison import FIELDS, REGISTRY, ROUTE
from validate_comparison_schema import validate_document
from workspace_evidence import schema_for


class WorkspaceAssemblyError(ValueError):
    pass


def assemble_workspace(capture, run_id, context, manifest, manifest_digest, forge_version, fixture_id, reproduce_command, repository_identity):
    required = {
        "format", "chain_id", "scenario_id", "actor", "target",
        "candidate", "expected_revert", "policy",
        "canonical_calldata", "comparison_scenario_key",
        "comparison_verdict", "comparison_reason",
    }
    for name in ("before", "after"):
        required.update(f"{name}_{field}" for field in FIELDS)
        required.update({
            f"{name}_expectedActiveImplementation",
            f"{name}_status",
            f"{name}_reason",
        })
    if not isinstance(capture, dict) or set(capture) != required:
        raise WorkspaceAssemblyError("Unexpected Direct raw capture fields")
    if capture["format"] != "protocol-sentinel-direct-capture-v1":
        raise WorkspaceAssemblyError("Unsupported Direct raw capture")
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise WorkspaceAssemblyError("Invalid run identity")
    if manifest["workspace"] != context.workspace:
        raise WorkspaceAssemblyError("Build workspace identity mismatch")
    versions = {unit["solcVersion"].split("+", 1)[0] for unit in manifest["units"]}
    if len(versions) != 1:
        raise WorkspaceAssemblyError("Mixed compiler versions")
    paths = {}
    for entry in manifest["integrationInputs"]:
        paths[entry["path"]] = entry["sha256"]
    for unit in manifest["units"]:
        for source in unit["sourceUnits"]:
            previous = paths.setdefault(source["path"], source["sha256"])
            if previous != source["sha256"]:
                raise WorkspaceAssemblyError("Source input identity collision")
    source_inputs = [
        {"path": name, "sha256": digest}
        for name, digest in sorted(paths.items())
    ]
    stages = {}
    for name in ("before", "after"):
        stages[name] = {
            "expectedActiveImplementation": capture[
                f"{name}_expectedActiveImplementation"
            ],
            "observation": {
                key: capture[f"{name}_{key}"] for key in FIELDS
            },
            "evaluation": {
                "status": capture[f"{name}_status"],
                "reason": capture[f"{name}_reason"],
            },
        }
    document = {
        "format": REGISTRY["format"],
        "schema_version": "1.1",
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
            "forgeVersion": forge_version,
            "solcVersion": next(iter(versions)),
        },
        "provenance": {
            "repository": repository_identity,
            "workspace": context.workspace,
            "toolPath": context.tool_path,
            "toolCommit": context.tool_commit,
            "sourceCommit": context.repository_commit,
            "workingTreeClean": True,
            "runId": run_id,
            "sourceInputs": source_inputs,
            "reproduceCommand": reproduce_command,
            "buildProvenance": {
                "format": "protocol-sentinel-build-provenance-v2",
                "manifestPath": "build/build-provenance.json",
                "manifestSha256": manifest_digest,
            },
        },
    }
    validate_document(document, schema=schema_for(document))
    return document
