#!/usr/bin/env python3
"""Portable Direct Evidence 1.1 runner for Git-pinned Foundry workspaces.

Fresh producer -> Git source closure -> isolated compiler replay ->
lossless Evidence -> independent classification -> optional trusted gate.
Legacy Evidence 1.0 and run_portable_direct.py remain unchanged.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from assemble_workspace_direct import assemble_workspace
from build_provenance import read_json
from replay_direct_comparison import replay
from replay_workspace_build import replay_unit
from run_direct_comparison import check_lossless
from producer_config import read_config
from run_portable_direct import verify_producer, write_json
from source_closure import attest_source
from trusted_workspace_gate import read_workspace_policy, evaluate_workspace_gate
from validate_comparison_schema import load_document
from workspace_context import resolve_workspace
from workspace_evidence import schema_for, verify_workspace_evidence
from workspace_provenance import capture_v2, verify_v2


class WorkspaceRunError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise WorkspaceRunError(message)


def git(root, *args):
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True,
        check=False,
    )
    require(result.returncode == 0, "Git command failed")
    return result.stdout.strip()


def run(project, tool, config_name, solc, policy_path=None):
    require(sys.version_info >= (3, 12), "Python 3.12 required")
    context = resolve_workspace(project, tool)
    require(
        Path(__file__).resolve()
        == context.tool_root / "scripts/run_workspace_direct.py",
        "Run installed, Git-pinned v0.6 entry point",
    )
    require(
        shutil.which("forge") is not None,
        "Foundry forge executable not found",
    )
    config_relative = Path(config_name)
    require(
        not config_relative.is_absolute()
        and ".." not in config_relative.parts
        and config_relative.suffix == ".toml",
        "Unsafe producer configuration path",
    )
    config_path = (context.project_root / config_relative).resolve()
    require(
        config_path.is_file()
        and config_path.is_relative_to(context.project_root),
        "Missing producer configuration",
    )
    attest_source(context, config_relative.as_posix())
    config = read_config(config_path)
    source = attest_source(context, config["source"])
    require(source.owner_path == ".", "Producer must be owned by consumer Git checkout")

    trusted = (
        read_workspace_policy(
            policy_path, context, os.environ,
        )
        if policy_path is not None else None
    )
    if trusted:
        require(
            context.workspace == trusted["policy"]["workspace"],
            "Trusted workspace mismatch",
        )
        for key in ("id", "scenario_id", "source", "contract", "test", "fixture_id"):
            require(
                config[key] == trusted["scenario"][key],
                "Producer is not selected by trusted policy",
            )

    base = (context.project_root / "artifacts/sentinel/runs").resolve()
    require(
        base.is_relative_to(context.project_root),
        "Evidence destination outside workspace",
    )
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "--", str(base / "probe")],
        cwd=context.repository_root, check=False,
    )
    require(
        ignored.returncode == 0,
        "Evidence output directory must be Git-ignored",
    )

    run_id = uuid.uuid4().hex
    staging = base / ".staging" / run_id
    completed = base / "completed" / run_id
    staging.mkdir(parents=True, exist_ok=False)

    try:
        raw_path = staging / "raw-capture.json"
        fresh = staging / ".fresh-build-info"
        env = os.environ.copy()
        env["FOUNDRY_DYNAMIC_TEST_LINKING"] = "false"
        env["SENTINEL_EXPORT_DIRECT"] = "true"
        env["SENTINEL_DIRECT_CAPTURE_PATH"] = str(
            raw_path.relative_to(context.project_root)
        )
        command = [
            "forge", "test", "--json", "--threads", "1",
            "--force", "--no-dynamic-test-linking",
            "--build-info", "--build-info-path", str(fresh),
            "--out", str(staging / ".forge-out"),
            "--cache-path", str(staging / ".forge-cache"),
            "--match-path", config["source"],
            "--match-contract", config["contract"],
            "--match-test", config["test"],
        ]
        print("=== Fresh Foundry producer ===", flush=True)
        result = subprocess.run(
            command, cwd=context.project_root, env=env,
            capture_output=True, text=True, timeout=480,
        )
        write_json(
            staging / "forge-results.json",
            {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )
        try:
            verify_producer(result.stdout, result.returncode, config)
        except ValueError:
            print(f"FORGE_EXIT_CODE={result.returncode}", file=sys.stderr)
            try:
                failure = json.loads(result.stdout)
                for suite, suite_info in failure.items():
                    for test_name, test_info in suite_info.get("test_results", {}).items():
                        if test_info.get("status") != "Success":
                            print(
                                "FORGE_TEST_FAILURE=" + json.dumps(
                                    {
                                        "suite": suite,
                                        "test": test_name,
                                        "status": test_info.get("status"),
                                        "reason": test_info.get("reason"),
                                    },
                                    sort_keys=True,
                                ),
                                file=sys.stderr,
                            )
            except (ValueError, AttributeError, TypeError):
                print("FORGE_STDOUT_TAIL=" + result.stdout[-2000:], file=sys.stderr)
            print("FORGE_STDERR_TAIL=" + result.stderr[-3000:], file=sys.stderr)
            raise
        require(raw_path.is_file() and raw_path.stat().st_size, "Missing raw capture")
        raw = load_document(raw_path)
        require(
            int(raw["scenario_id"], 16) == int(config["scenario_id"], 16),
            "Captured scenario ID differs from trusted producer",
        )
        print("PASS | Fresh producer and scenario", flush=True)

        bundle = staging / "build"
        manifest_digest = capture_v2(
            context, fresh, bundle, config["source"],
        )
        manifest = read_json(bundle / "build-provenance.json")
        print("PASS | Git-attested compiler source closure", flush=True)

        reproduced = 0
        source_count = 0
        for unit in manifest["units"]:
            info = read_json(bundle / unit["file"])
            outcome = replay_unit(context, info, solc)
            reproduced += outcome["contracts"]
            source_count += outcome["source_units"]
        require(reproduced > 0, "No independently reproduced contracts")
        print(
            f"PASS | Isolated compiler replay: {reproduced} contracts",
            flush=True,
        )

        forge_version = subprocess.check_output(
            ["forge", "--version"], text=True
        ).strip().splitlines()[0]
        command_display = (
            "forge test --no-dynamic-test-linking "
            f"--match-path {config['source']} "
            f"--match-contract {config['contract']} "
            f"--match-test {config['test']}"
        )
        document = assemble_workspace(
            raw, run_id, context, manifest, manifest_digest,
            forge_version, config["fixture_id"], command_display,
            (
                trusted["policy"]["consumer_repository"]
                if trusted is not None else "LOCAL_UNTRUSTED_CHECKOUT"
            ),
        )
        check_lossless(raw, document)
        verify_workspace_evidence(
            document, context, manifest_digest,
            (
                trusted["policy"]["consumer_repository"]
                if trusted is not None else "LOCAL_UNTRUSTED_CHECKOUT"
            ),
            manifest,
        )
        report = replay(document, schema=schema_for(document))
        require(
            report["schema"] == "VALID"
            and report["classification_replay"] == "MATCH",
            "Independent Direct classification replay failed",
        )
        print("PASS | Lossless Evidence and Python replay", flush=True)

        # Re-attest all sources and Gitlinks immediately before publication.
        current = resolve_workspace(context.project_root, context.tool_root)
        require(current == context, "Consumer or tool identity changed during run")
        require(
            verify_v2(current, bundle, config["source"]) == manifest_digest,
            "Build provenance changed after compiler replay",
        )
        for source_input in document["provenance"]["sourceInputs"]:
            physical = (current.repository_root / source_input["path"]).resolve()
            require(
                physical.is_file()
                and physical.is_relative_to(current.repository_root),
                "Source input path changed",
            )
            import hashlib
            require(
                hashlib.sha256(physical.read_bytes()).hexdigest()
                == source_input["sha256"],
                "Source input byte hash changed",
            )

        gate_result = (
            evaluate_workspace_gate(
                trusted, current, config, document, report, run_id
            ) if trusted is not None else None
        )
        write_json(staging / "evidence.json", document)
        write_json(
            staging / "verification.json",
            {
                **report,
                "producer_test": "Success",
                "source_context": "GIT_ATTESTED_WORKSPACE",
                "build_provenance": "VERIFIED_V2",
                "build_replay": "ISOLATED_COMPILER_OUTPUT_MATCH",
                "reproduced_contracts": reproduced,
                "source_units_checked": source_count,
                "execution_provenance": "UNAUTHENTICATED",
                "tool_revision": context.tool_commit,
                "run_id": run_id,
                "publication": "COMPLETED",
                "ci_decision": (
                    gate_result["decision"]
                    if gate_result else "NOT_EVALUATED"
                ),
            },
        )
        if gate_result is not None:
            write_json(staging / "ci-gate.json", gate_result)

        for name in (".fresh-build-info", ".forge-out", ".forge-cache"):
            candidate = staging / name
            if candidate.exists():
                shutil.rmtree(candidate)
        require(not completed.exists(), "Completed Evidence already exists")
        completed.parent.mkdir(parents=True, exist_ok=True)
        staging.rename(completed)
        decision = gate_result["decision"] if gate_result else "NOT_EVALUATED"
        print("CLASSIFICATION:", report["comparison"])
        print("REPLAY: MATCH")
        print("CI DECISION:", decision)
        print("COMPLETED:", completed)
        return decision

    except Exception:
        print("FAILED | No completed Evidence published", file=sys.stderr)
        print("Diagnostic staging:", staging, file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--tool-root", type=Path)
    parser.add_argument("--config", required=True)
    parser.add_argument("--solc", required=True, type=Path)
    parser.add_argument("--trusted-policy", type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    tool = (
        args.tool_root.resolve()
        if args.tool_root
        else project / "lib/protocol-sentinel"
    )
    return run(
        project, tool, args.config, args.solc.resolve(),
        policy_path=args.trusted_policy,
    )


if __name__ == "__main__":
    ci_mode = "--trusted-policy" in sys.argv or any(
        x.startswith("--trusted-policy=") for x in sys.argv
    )
    try:
        outcome = main()
    except Exception as exc:
        if ci_mode:
            print("CI DECISION: BLOCK", file=sys.stderr)
            print(f"WORKSPACE GATE FAILED: {exc}", file=sys.stderr)
            raise SystemExit(2) from exc
        raise SystemExit(f"WORKSPACE RUN FAILED: {exc}") from exc
    raise SystemExit({
        "NOT_EVALUATED": 0,
        "PASS": 0,
        "BLOCK": 2,
        "REVIEW": 3,
    }[outcome])
