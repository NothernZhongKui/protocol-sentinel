#!/usr/bin/env python3
"""Portable Direct EOA/UUPS Evidence runner.

Verifies execution, source inputs, classification and compiler replay.
Does not authenticate execution or decide CI merge policy.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import uuid
from pathlib import Path

from assemble_direct_comparison import assemble
from build_provenance import (
    attach_evidence_build,
    capture_bundle,
    read_json,
    verify_evidence_build,
)
from replay_build_compilation import verify_build_units
from replay_direct_comparison import replay
from run_direct_comparison import check_lossless
from validate_comparison_schema import (
    invalid_constant,
    load_document,
    unique_keys,
    validate_document,
)

TOOLS = (
    "scripts/run_portable_direct.py",
    "scripts/assemble_direct_comparison.py",
    "scripts/build_provenance.py",
    "scripts/replay_build_compilation.py",
    "scripts/replay_direct_comparison.py",
    "scripts/run_direct_comparison.py",
    "scripts/validate_comparison_schema.py",
    "evidence/schema/comparison-1.0.schema.json",
    "evidence/semantics/registry.json",
)

IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
SCENARIO = re.compile(r"0x[0-9a-fA-F]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(root, *args):
    return subprocess.check_output(
        ["git", *args],
        cwd=root,
        text=True,
        stderr=subprocess.PIPE,
    ).strip()


def read_config(path):
    document = tomllib.loads(path.read_text(encoding="utf-8"))

    require(
        set(document) == {"sentinel", "producer"},
        "Invalid configuration sections",
    )

    require(
        document["sentinel"] == {
            "config_version": "1",
            "route": "DIRECT_EOA_UUPS",
        },
        "Unsupported Sentinel configuration",
    )

    producer = document["producer"]
    required = {
        "id",
        "contract",
        "test",
        "source",
        "fixture_id",
        "scenario_id",
    }

    require(
        isinstance(producer, dict) and set(producer) == required,
        "Invalid producer configuration",
    )

    for field in ("id", "contract", "test"):
        value = producer[field]
        require(
            isinstance(value, str) and IDENT.fullmatch(value),
            f"Invalid producer {field}",
        )

    require(
        producer["test"].startswith("test_"),
        "Not a Foundry test",
    )

    fixture = producer["fixture_id"]
    require(
        isinstance(fixture, str) and 0 < len(fixture) <= 128,
        "Invalid fixture ID",
    )

    scenario = producer["scenario_id"]
    require(
        isinstance(scenario, str) and SCENARIO.fullmatch(scenario),
        "Invalid scenario ID",
    )

    source = producer["source"]
    require(
        isinstance(source, str),
        "Invalid producer source",
    )

    relative = Path(source)
    require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and source.startswith("test/")
        and source.endswith(".sol"),
        "Unsafe producer source path",
    )

    return producer


def verify_tool_pin(project):
    installed = (project / "lib/protocol-sentinel").resolve()

    require(
        installed.is_relative_to(project),
        "External Sentinel dependency path",
    )

    require(
        Path(__file__).resolve()
        == installed / "scripts/run_portable_direct.py",
        "Run the installed, pinned Sentinel entry point",
    )

    revision = git(installed, "rev-parse", "HEAD")

    index = git(
        project,
        "ls-files",
        "--stage",
        "--",
        "lib/protocol-sentinel",
    ).split()

    require(
        len(index) == 4
        and index[0] == "160000"
        and index[1] == revision
        and index[3] == "lib/protocol-sentinel",
        "Sentinel revision differs from consumer Git index",
    )

    require(
        not git(
            installed,
            "status",
            "--porcelain",
            "--untracked-files=all",
        ),
        "Dirty Sentinel dependency",
    )

    return revision


def source_inputs(project, bundle, config_name):
    manifest = read_json(bundle / "build-provenance.json")

    names = {
        ".gitmodules",
        "foundry.toml",
        "foundry.lock",
        config_name,
    }

    for unit in manifest["units"]:
        info = read_json(bundle / unit["file"])
        names.update(info["input"]["sources"])

    names.update(
        "lib/protocol-sentinel/" + name
        for name in TOOLS
    )

    entries = []

    for name in sorted(names):
        path = (project / name).resolve()

        require(
            path.is_relative_to(project) and path.is_file(),
            f"Missing or unsafe source input: {name}",
        )

        entries.append({
            "path": name,
            "sha256": hashlib.sha256(
                path.read_bytes()
            ).hexdigest(),
        })

    return entries


def verify_producer(stdout, exit_code, config):
    result = json.loads(
        stdout,
        object_pairs_hook=unique_keys,
        parse_constant=invalid_constant,
    )

    tests = [
        (suite_name, name, entry.get("status"))
        for suite_name, suite in result.items()
        for name, entry in suite.get(
            "test_results", {}
        ).items()
    ]

    require(
        exit_code == 0 and len(tests) == 1,
        f"Producer failed or ambiguous: {tests}",
    )

    suite, test, status = tests[0]

    require(
        suite.endswith(
            config["source"] + ":" + config["contract"]
        )
        and test == config["test"] + "()"
        and status == "Success",
        f"Unexpected producing test: {tests}",
    )


def write_json(path, document):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(
            document,
            stream,
            indent=2,
            sort_keys=True,
        )
        stream.write("\n")


def run(project, config, config_name):
    require(
        not git(project, "status", "--porcelain"),
        "Consumer checkout must be clean",
    )

    source = (project / config["source"]).resolve()

    require(
        source.is_relative_to(project) and source.is_file(),
        "Missing producer source",
    )

    require(
        (project / "foundry.lock").is_file(),
        "Missing committed Foundry lockfile",
    )

    revision = verify_tool_pin(project)

    require(
        git(
            project,
            "ls-files",
            "--error-unmatch",
            "--",
            config_name,
        ) == config_name,
        "Configuration must be committed",
    )

    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "-q",
            "artifacts/sentinel/runs/probe",
        ],
        cwd=project,
        check=False,
    )

    require(
        ignored.returncode == 0,
        "Evidence output directory must be Git-ignored",
    )

    run_id = uuid.uuid4().hex
    base = project / "artifacts/sentinel/runs"

    staging = base / ".staging" / run_id
    completed = base / "completed" / run_id

    staging.mkdir(parents=True, exist_ok=False)

    capture = staging / "raw-capture.json"
    evidence_path = staging / "evidence.json"
    build = staging / "build"

    fresh_info = staging / ".fresh-build-info"
    forge_out = staging / ".forge-out"
    forge_cache = staging / ".forge-cache"

    try:
        env = os.environ.copy()
        env["FOUNDRY_DYNAMIC_TEST_LINKING"] = "false"
        env["SENTINEL_EXPORT_DIRECT"] = "true"
        env["SENTINEL_DIRECT_CAPTURE_PATH"] = str(
            capture.relative_to(project)
        )

        command = [
            "forge",
            "test",
            "--json",
            "--threads", "1",
            "--force",
            "--no-dynamic-test-linking",
            "--build-info",
            "--build-info-path", str(fresh_info),
            "--out", str(forge_out),
            "--cache-path", str(forge_cache),
            "--match-path", config["source"],
            "--match-contract", config["contract"],
            "--match-test", config["test"],
        ]

        print("=== Fresh external producer ===", flush=True)

        result = subprocess.run(
            command,
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=360,
        )

        write_json(
            staging / "forge-results.json",
            {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )

        verify_producer(
            result.stdout,
            result.returncode,
            config,
        )

        require(
            capture.is_file()
            and capture.stat().st_size > 0,
            "Producer did not export a capture",
        )

        raw = load_document(capture)

        require(
            int(raw["scenario_id"], 16)
            == int(config["scenario_id"], 16),
            "Captured scenario differs from configuration",
        )

        print("PASS | Producer and scenario", flush=True)

        capture_bundle(
            fresh_info,
            build,
            project,
            run_id,
            config["source"],
        )

        inputs = source_inputs(
            project,
            build,
            config_name,
        )

        base_command = (
            "forge test --no-dynamic-test-linking "
            f"--match-path {config['source']} "
            f"--match-contract {config['contract']} "
            f"--match-test {config['test']}"
        )

        context = {
            "projectRoot": str(project),
            "fixtureId": config["fixture_id"],
            "repository": project.name,
            "sourceInputs": inputs,
            "reproduceCommand": base_command,
        }

        document, _ = assemble(
            raw,
            run_id,
            context=context,
        )

        require(
            document["provenance"]["workingTreeClean"] is True,
            "Dirty checkout during assembly",
        )

        require(
            document["provenance"]["sourceCommit"]
            == git(project, "rev-parse", "HEAD"),
            "Consumer revision changed",
        )

        check_lossless(raw, document)

        attach_evidence_build(
            document,
            build,
            project,
            run_id,
            config["source"],
            base_command,
        )

        validate_document(document)

        verify_evidence_build(
            document,
            build,
            project,
            run_id,
            config["source"],
            base_command,
        )

        print("PASS | Source and build provenance", flush=True)

        report = replay(document)

        require(
            report["schema"] == "VALID"
            and report["classification_replay"] == "MATCH",
            "Independent classification replay failed",
        )

        print("PASS | Independent Python replay", flush=True)

        require(
            verify_build_units(build) > 0,
            "No independently reproduced contracts",
        )

        print("PASS | Independent compiler replay", flush=True)

        require(
            not git(project, "status", "--porcelain"),
            "Consumer checkout changed during execution",
        )

        require(
            all(
                hashlib.sha256(
                    (project / entry["path"]).read_bytes()
                ).hexdigest() == entry["sha256"]
                for entry in inputs
            ),
            "Source input changed during verification",
        )

        write_json(evidence_path, document)

        write_json(
            staging / "verification.json",
            {
                **report,
                "producer_test": "Success",
                "source_context": "MATCHED_LOCAL_CHECKOUT",
                "build_provenance": "LOCAL_INPUTS_VERIFIED",
                "build_replay": "NORMALIZED_OUTPUT_MATCH",
                "execution_provenance": "UNAUTHENTICATED",
                "tool_revision": revision,
                "run_id": run_id,
                "publication": "COMPLETED",
                "ci_decision": "NOT_EVALUATED",
            },
        )

        for temporary in (
            fresh_info,
            forge_out,
            forge_cache,
        ):
            if temporary.exists():
                shutil.rmtree(temporary)

        require(
            not completed.exists(),
            "Completed run directory already exists",
        )

        completed.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        staging.rename(completed)

        print()
        print("SCENARIO:", config["id"])
        print("CLASSIFICATION:", report["comparison"])
        print("REPLAY: MATCH")
        print("CI DECISION: NOT_EVALUATED")
        print("COMPLETED:", completed)

    except Exception:
        print(
            "FAILED | No completed evidence published",
            file=sys.stderr,
        )
        print(
            "Diagnostic staging:",
            staging,
            file=sys.stderr,
        )
        raise


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=Path("sentinel.toml"),
    )

    args = parser.parse_args()

    project = args.project.resolve()
    config_path = (project / args.config).resolve()

    require(
        config_path.is_relative_to(project)
        and config_path.is_file(),
        "Missing or unsafe consumer configuration",
    )

    require(
        not args.config.is_absolute()
        and ".." not in args.config.parts
        and args.config.suffix == ".toml",
        "Unsafe configuration name",
    )

    run(
        project,
        read_config(config_path),
        args.config.as_posix(),
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            f"PORTABLE RUN FAILED | {exc}"
        ) from exc
