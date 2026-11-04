#!/usr/bin/env python3
"""Independently verify a completed v0.6 Direct workspace run.

Re-read the recorded producer result, raw capture, Evidence 1.1,
Git-attested build manifest v2, and independently recompile every unit
with the chosen exact solc. Recompute trusted CI PASS/BLOCK/REVIEW.

This checks a local, Git-pinned checkout. It does NOT cryptographically
authenticate the original EVM execution or a remote untrusted machine.
Legacy 1.0 artifacts must use the legacy verifier.
"""

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

from build_provenance import read_json
from replay_direct_comparison import replay
from replay_workspace_build import replay_unit
from run_direct_comparison import check_lossless
from run_portable_direct import read_config, verify_producer
from source_closure import attest_source
from trusted_workspace_gate import read_workspace_policy, evaluate_workspace_gate
from validate_comparison_schema import load_document
from workspace_context import resolve_workspace
from workspace_evidence import schema_for, verify_workspace_evidence
from workspace_provenance import verify_v2


class CompletedRunError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CompletedRunError(message)


def expected_sources(manifest):
    sources = {}
    for config in manifest["integrationInputs"]:
        name, digest = config["path"], config["sha256"]
        require(name not in sources, "Duplicate integration source identity")
        sources[name] = digest
    for unit in manifest["units"]:
        for source in unit["sourceUnits"]:
            name, digest = source["path"], source["sha256"]
            require(
                name not in sources or sources[name] == digest,
                "Contradictory compiler source identity",
            )
            sources[name] = digest
    return [
        {"path": name, "sha256": digest}
        for name, digest in sorted(sources.items())
    ]


def verify_completed(project, tool, run_directory, solc, config_name, policy_path, environ):
    context = resolve_workspace(project, tool)
    require(
        Path(__file__).resolve() == context.tool_root / "scripts/verify_workspace_run.py",
        "Verifier must be the Git-pinned installed tool",
    )

    config_path = Path(config_name)
    require(
        not config_path.is_absolute()
        and ".." not in config_path.parts
        and config_path.suffix == ".toml",
        "Unsafe configuration name",
    )
    attest_source(context, config_path.as_posix())
    config = read_config(context.project_root / config_path)
    attest_source(context, config["source"])

    trusted = read_workspace_policy(policy_path, context, environ)
    for field in ("id", "scenario_id", "source", "contract", "test", "fixture_id"):
        require(
            trusted["scenario"][field] == config[field],
            "Trusted policy does not select recorded producer",
        )

    completed_root = (
        context.project_root / "artifacts/sentinel/runs/completed"
    ).resolve()
    supplied = Path(run_directory)
    require(not supplied.is_symlink(), "Symlinked run directory")
    run_dir = supplied.resolve()
    require(
        run_dir.parent == completed_root
        and re.fullmatch(r"[0-9a-f]{32}", run_dir.name) is not None
        and run_dir.is_dir(),
        "Run is not a completed v0.6 artifact",
    )
    required_names = {
        "raw-capture.json", "evidence.json", "verification.json",
        "forge-results.json", "ci-gate.json", "build",
    }
    require(
        {p.name for p in run_dir.iterdir()} == required_names,
        "Completed artifact file set mismatch",
    )
    for name in required_names - {"build"}:
        path = run_dir / name
        require(path.is_file() and not path.is_symlink(), "Invalid artifact file")

    raw = load_document(run_dir / "raw-capture.json")
    doc = load_document(run_dir / "evidence.json")
    require(doc.get("schema_version") == "1.1", "Evidence downgrade or unknown version")

    bundle = run_dir / "build"
    require(bundle.is_dir() and not bundle.is_symlink(), "Invalid build directory")
    manifest_sha = verify_v2(context, bundle, config["source"])
    manifest = read_json(bundle / "build-provenance.json")
    verify_workspace_evidence(
        doc, context, manifest_sha, trusted["policy"]["consumer_repository"],
    )
    require(
        doc["provenance"]["runId"] == run_dir.name,
        "Completed directory and Evidence run identity mismatch",
    )
    require(
        doc["provenance"]["sourceInputs"] == expected_sources(manifest),
        "Evidence source input closure mismatch",
    )
    for entry in doc["provenance"]["sourceInputs"]:
        path = (context.repository_root / entry["path"]).resolve()
        require(
            path.is_file() and path.is_relative_to(context.repository_root),
            "Source input missing or outside checkout",
        )
        require(
            hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"],
            "Source input SHA-256 differs",
        )

    check_lossless(raw, doc)
    forge = read_json(run_dir / "forge-results.json")
    require(
        isinstance(forge, dict)
        and set(forge) == {"exit_code", "stdout", "stderr"}
        and type(forge["exit_code"]) is int
        and isinstance(forge["stdout"], str)
        and isinstance(forge["stderr"], str),
        "Invalid recorded producer result",
    )
    verify_producer(forge["stdout"], forge["exit_code"], config)
    require(
        int(raw["scenario_id"], 16) == int(config["scenario_id"], 16),
        "Producer scenario identity mismatch",
    )
    report = replay(doc, schema=schema_for(doc))
    require(
        report["classification_replay"] == "MATCH"
        and report["schema"] == "VALID",
        "Independent classification replay failed",
    )
    gate = evaluate_workspace_gate(
        trusted, context, config, doc, report, run_dir.name,
    )
    require(
        read_json(run_dir / "ci-gate.json") == gate,
        "Published trusted CI gate differs from independently computed decision",
    )

    # Re-execute every compiler unit, not just verify the recorded digest.
    reproduced = 0
    attested_units = 0
    for unit in manifest["units"]:
        outcome = replay_unit(
            context, read_json(bundle / unit["file"]), solc
        )
        reproduced += outcome["contracts"]
        attested_units += outcome["source_units"]
    require(reproduced > 0, "No independently reproduced compiler output")
    expected_report = {
        **report,
        "producer_test": "Success",
        "source_context": "GIT_ATTESTED_WORKSPACE",
        "build_provenance": "VERIFIED_V2",
        "build_replay": "ISOLATED_COMPILER_OUTPUT_MATCH",
        "reproduced_contracts": reproduced,
        "source_units_checked": attested_units,
        "execution_provenance": "UNAUTHENTICATED",
        "tool_revision": context.tool_commit,
        "run_id": run_dir.name,
        "publication": "COMPLETED",
        "ci_decision": gate["decision"],
    }
    require(
        read_json(run_dir / "verification.json") == expected_report,
        "Published verification report differs from independent replay",
    )
    return {
        "run_id": run_dir.name,
        "classification": report["comparison"],
        "decision": gate["decision"],
        "contracts": reproduced,
        "source_units": attested_units,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--tool-root", type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--solc", required=True, type=Path)
    parser.add_argument("--trusted-policy", required=True, type=Path)
    args = parser.parse_args()

    project = args.project.resolve()
    tool = (
        args.tool_root.resolve() if args.tool_root
        else project / "lib/protocol-sentinel"
    )
    import os
    result = verify_completed(
        project, tool, args.run_dir, args.solc.resolve(),
        args.config, args.trusted_policy, os.environ,
    )
    print(f"RUN_ID={result['run_id']}")
    print(f"CLASSIFICATION={result['classification']}")
    print(f"CONTRACTS={result['contracts']}")
    print(f"SOURCE_UNITS={result['source_units']}")
    print("PUBLISHED_EVIDENCE=INDEPENDENTLY_REVERIFIED")
    print(f"CI_DECISION={result['decision']}")
    return result["decision"]


if __name__ == "__main__":
    try:
        decision = main()
    except Exception as exc:
        print(f"COMPLETED_RUN_REJECTED: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit({"PASS": 0, "BLOCK": 0, "REVIEW": 0}[decision])
