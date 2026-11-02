#!/usr/bin/env python3
"""Write a sanitized, reproducible mainnet fork test report."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import tempfile

from datetime import datetime, timezone
from pathlib import Path

from verify_fork_results import load_results, validate_results

SOURCE_FILES = [
    "src/AuthorityProbe.sol",
    "test/Adapter8004MainnetFork.t.sol",
    "test/fixtures/AdapterForkUpgradeVariants.sol",
    "scripts/reproduce_adapter8004_fork.sh",
    "scripts/verify_fork_results.py",
    "scripts/write_fork_report.py",
    "foundry.toml",
]


def command_output(*command):
    return subprocess.check_output(
        command,
        text=True,
        stderr=subprocess.PIPE,
        timeout=30,
    ).strip()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_report(results_path, block_hash, implementation, owner):
    statuses = validate_results(load_results(results_path))

    dirty = bool(
        command_output(
            "git", "status", "--porcelain",
            "--untracked-files=normal",
        )
    )

    return {
        "format": "protocol-sentinel-fork-report-v1",
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds"),
        "repository": "NothernZhongKui/protocol-sentinel",
        "git_commit": command_output("git", "rev-parse", "HEAD"),
        "working_tree_clean": not dirty,
        "source_sha256": {
            path: sha256_file(path)
            for path in SOURCE_FILES
        },
        "tool_versions": {
            "forge": command_output("forge", "--version"),
            "cast": command_output("cast", "--version"),
            "python": platform.python_version(),
        },
        "fork": {
            "chain_id": 1,
            "block_number": 24995819,
            "block_hash": block_hash,
            "proxy": "0xde152AfB7db5373F34876E1499fbD893A82dD336",
            "implementation": implementation,
            "historical_owner": owner,
            "upgrade_candidate": "0xA54a604448A5Ab0AfFccdDa6228EC4F2ac12a586",
        },
        "execution": {
            "mode": "local Foundry historical fork",
            "required_tests": len(statuses),
            "tests": statuses,
            "all_required_success": True,
        },
        "interpretation": (
            "Tests include an intentionally introduced "
            "PASS -> FAIL -> PASS authority regression. "
            "The over-permissive implementation is test-only. "
            "This report does not claim a vulnerability "
            "in the historical Adapter8004 deployment."
        ),
        "limitations": (
            "The report summarizes validated Foundry test statuses. "
            "It is not a signed Ethereum execution proof and "
            "does not contain individual Solidity observations."
        ),
    }


def write_report(report, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=".fork-report-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--block-hash", required=True)
    parser.add_argument("--implementation", required=True)
    parser.add_argument("--owner", required=True)
    args = parser.parse_args()

    report = build_report(
        args.results,
        args.block_hash,
        args.implementation,
        args.owner,
    )

    write_report(report, args.output)

    print(f"PASS | Fork evidence saved: {args.output}")


if __name__ == "__main__":
    main()
