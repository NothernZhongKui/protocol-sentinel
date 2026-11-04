#!/usr/bin/env python3
"""Standalone v0.6 research replay of one Foundry compiler build unit.

Fail closed unless every source is Git-attested and an isolated snapshot
reproduces recorded output using the exact chosen compiler. This module
does NOT authenticate the producer execution, publish Evidence or decide CI.
"""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from replay_build_compilation import canonical, verify_outputs
from source_closure import attest_build_sources, materialize_imports
from workspace_context import resolve_workspace


class ReplayError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReplayError(message)


def compiler_version(solc):
    result = subprocess.run(
        [str(solc), "--version"],
        text=True, capture_output=True, check=False,
        timeout=30,
    )
    require(result.returncode == 0, "Compiler version unavailable")
    found = re.search(r"Version:\s*(0\.\d+\.\d+\+commit\.[0-9a-f]{8})", result.stdout)
    require(found is not None, "Invalid solc version string")
    return found.group(1)


def replay_unit(context, info, solc):
    require(isinstance(info, dict), "Invalid build-info")
    require(
        set(("language", "sources", "settings")).issubset(
            info.get("input", {})
        ),
        "Incomplete standard compiler input",
    )
    require(isinstance(info.get("output"), dict), "Missing original compiler output")
    require(isinstance(info.get("solcVersion"), str), "Missing recorded solc version")
    observed = compiler_version(solc)
    require(
        observed.startswith(info["solcVersion"].split("+", 1)[0] + "+"),
        "Compiler version mismatch",
    )
    if "+" in info["solcVersion"]:
        require(
            observed.startswith(info["solcVersion"]),
            "Compiler commit mismatch",
        )

    attested = attest_build_sources(context, info)
    standard = {key: info["input"][key] for key in ("language", "sources", "settings")}
    original_digest = hashlib.sha256(canonical(standard)).hexdigest()

    with tempfile.TemporaryDirectory(prefix="sentinel-replay-") as temp:
        sandbox = Path(temp).resolve()
        snapshot_workspace = sandbox / context.workspace
        snapshot_workspace.mkdir(parents=True, exist_ok=True)
        missing_imports = materialize_imports(context, attested, snapshot_workspace)
        require(
            hashlib.sha256(canonical(standard)).hexdigest() == original_digest,
            "Compiler input mutated during snapshot",
        )
        command = [
            str(solc),
            "--standard-json",
            "--base-path", str(snapshot_workspace),
            "--allow-paths", str(sandbox),
        ]
        process = subprocess.run(
            command,
            cwd=snapshot_workspace,
            input=canonical(standard),
            capture_output=True,
            timeout=300,
        )
        require(process.returncode == 0, "Compiler subprocess failed")
        raw = process.stdout.decode("utf-8-sig")
        if raw.startswith(">>>"):
            raw = raw.split("\n", 1)[1]
        try:
            output = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ReplayError("Invalid compiler output JSON") from exc
        errors = [e for e in output.get("errors", []) if e.get("severity") == "error"]
        require(not errors, "Compiler errors during isolated replay")
        require(
            set(info["output"]["sources"]) == set(output.get("sources", {})),
            "Compiled source-unit set differs",
        )
        count = verify_outputs(info["output"], output)
        return {
            "result": "ISOLATED_COMPILER_OUTPUT_MATCH",
            "contracts": count,
            "source_units": len(attested),
            "snapshot_imports": len(missing_imports),
            "solc": observed,
            "original_input_sha256": original_digest,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--tool-root", type=Path, required=True)
    parser.add_argument("--expected-workspace", required=True)
    parser.add_argument("--build-info", type=Path, required=True)
    parser.add_argument("--solc", type=Path, required=True)
    args = parser.parse_args()

    context = resolve_workspace(
        args.project, args.tool_root,
        expected_workspace=args.expected_workspace,
    )
    info = json.loads(args.build_info.read_text(encoding="utf-8"))
    result = replay_unit(context, info, args.solc)
    for key, value in result.items():
        print(f"{key.upper()}={value}")
    print("EVIDENCE=NOT_EVALUATED")
    print("CI_DECISION=NOT_EVALUATED")


if __name__ == "__main__":
    try:
        main()
    except (ReplayError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"ISOLATED_REPLAY_FAILED: {exc}") from exc
