#!/usr/bin/env python3
"""Mutation tests for published v0.6 Evidence, without another Forge run.

Each case changes exactly one completed artifact, invokes the independently
installed verifier, requires a specific fail-closed reason, and restores
the original bytes even if the assertion fails. Intended for temporary
acceptance workspaces only, not live production artifact directories.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path


def mutate_json(path, change):
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")


def rejected(label, artifact, change, expected_reason, command):
    original = artifact.read_bytes()
    try:
        mutate_json(artifact, change)
        outcome = subprocess.run(
            command, capture_output=True, text=True, timeout=120,
            check=False, env=os.environ.copy(),
        )
        diagnostics = outcome.stdout + outcome.stderr
        if outcome.returncode != 2 or (
            "COMPLETED_RUN_REJECTED:" not in diagnostics
            or expected_reason not in diagnostics
        ):
            raise AssertionError(
                f"{label}: expected reject reason {expected_reason!r}, "
                f"exit={outcome.returncode}, diagnostics={diagnostics[-1500:]!r}"
            )
        print(f"PASS | Reject {label}: {expected_reason}", flush=True)
    finally:
        artifact.write_bytes(original)
    if artifact.read_bytes() != original:
        raise AssertionError(f"Could not restore {label}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--verifier", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--tool-root", type=Path, required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--solc", type=Path, required=True)
    parser.add_argument("--trusted-policy", type=Path, required=True)
    args = parser.parse_args()
    completed = args.run_dir.resolve()

    command = [
        "python3", "-B", str(args.verifier),
        "--project", str(args.project),
        "--tool-root", str(args.tool_root),
        "--run-dir", str(completed),
        "--config", args.config,
        "--solc", str(args.solc),
        "--trusted-policy", str(args.trusted_policy),
    ]
    evidence = completed / "evidence.json"
    raw = completed / "raw-capture.json"
    gate = completed / "ci-gate.json"
    manifest = completed / "build/build-provenance.json"
    manifest_doc = json.loads(manifest.read_text())
    unit = completed / "build" / manifest_doc["units"][0]["file"]

    def set_key(key, value):
        return lambda doc: doc.__setitem__(key, value)

    rejected(
        "raw capture verdict swap",
        raw,
        set_key("comparison_verdict", "CHANGED_TO_VIOLATION"),
        "Lossless mismatch: comparison_verdict",
        command,
    )
    rejected(
        "Evidence schema downgrade",
        evidence,
        set_key("schema_version", "1.0"),
        "Evidence downgrade or unknown version",
        command,
    )
    rejected(
        "Evidence compiler version substitution",
        evidence,
        lambda doc: doc["environment"].__setitem__("solcVersion", "0.8.24"),
        "Evidence compiler version differs from manifest",
        command,
    )
    rejected(
        "Evidence execution mode substitution",
        evidence,
        lambda doc: doc["environment"].__setitem__("executionMode", "fork"),
        "Unsupported workspace execution mode",
        command,
    )
    rejected(
        "Evidence consumer commit substitution",
        evidence,
        lambda doc: doc["provenance"].__setitem__("sourceCommit", "a" * 40),
        "Workspace Evidence mismatch: sourceCommit",
        command,
    )
    rejected(
        "build provenance workspace substitution",
        manifest,
        set_key("workspace", "projects/other"),
        "V2 manifest does not match Git-attested build",
        command,
    )
    rejected(
        "compiler build-info output mutation",
        unit,
        lambda doc: doc["output"].__setitem__("contracts", {"forged": {}}),
        "V2 manifest does not match Git-attested build",
        command,
    )
    rejected(
        "published trusted CI decision substitution",
        gate,
        set_key("decision", "BLOCK"),
        "Published trusted CI gate differs",
        command,
    )
    print("=== COMPLETED EVIDENCE TAMPER CONTROLS PASSED ===")


if __name__ == "__main__":
    main()
