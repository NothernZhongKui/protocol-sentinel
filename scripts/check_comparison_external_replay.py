#!/usr/bin/env python3
"""Reproduce published comparison evidence outside the repository.

Copies only replay modules, schema, semantics and evidence.
No Solidity source, Foundry, Git or RPC is needed by the consumer.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPLAY_FILES = (
    "scripts/validate_comparison_schema.py",
    "scripts/replay_direct_comparison.py",
    "scripts/replay_timelock_comparison.py",
    "evidence/schema/comparison-1.0.schema.json",
    "evidence/semantics/registry.json",
)

CASES = {
    "direct": {
        "script": "replay_direct_comparison.py",
        "verdict": "CHANGED_TO_VIOLATION",
        "before": "PASS",
        "after": "FAIL",
    },
    "ready": {
        "script": "replay_timelock_comparison.py",
        "verdict": "STILL_SATISFIED",
        "before": "PASS",
        "after": "PASS",
    },
    "waiting": {
        "script": "replay_timelock_comparison.py",
        "verdict": "STILL_SATISFIED",
        "before": "PASS",
        "after": "PASS",
    },
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare_consumer(base, evidence):
    consumer = base / "consumer"

    for name in REPLAY_FILES:
        destination = consumer / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)

    evidence_dir = consumer / "evidence-files"
    evidence_dir.mkdir(parents=True)

    copied = {}

    for label, original in evidence.items():
        destination = evidence_dir / f"{label}.json"

        shutil.copyfile(original, destination)

        require(
            digest(original) == digest(destination),
            f"{label}: evidence changed during copying",
        )

        copied[label] = destination

    require(
        not (consumer / "src").exists(),
        "Solidity source unexpectedly copied",
    )

    require(
        not (consumer / "foundry.toml").exists(),
        "Foundry configuration unexpectedly copied",
    )

    require(
        not (consumer / ".git").exists(),
        "Repository history unexpectedly copied",
    )

    return consumer, copied


def isolated_environment(base):
    # No executable lookup through the host PATH.
    empty_bin = base / "empty-bin"
    empty_bin.mkdir()

    home = base / "home"
    home.mkdir()

    env = os.environ.copy()

    for name in list(env):
        if (
            name in (
                "PYTHONPATH",
                "PYTHONHOME",
                "VIRTUAL_ENV",
                "ETH_RPC_URL",
                "WEB3_PROVIDER_URI",
            )
            or name.startswith("FOUNDRY_")
            or name.startswith("CAST_")
            or name.endswith("_RPC_URL")
        ):
            env.pop(name, None)

    env["PATH"] = str(empty_bin)
    env["HOME"] = str(home)
    env["PYTHONNOUSERSITE"] = "1"

    require(
        shutil.which("forge", path=env["PATH"]) is None,
        "Foundry is visible",
    )

    require(
        shutil.which("cast", path=env["PATH"]) is None,
        "Cast is visible",
    )

    return env


def run_replay(consumer, env, label, evidence_path):
    script = (
        consumer / "scripts"
        / CASES[label]["script"]
    )

    return subprocess.run(
        [
            sys.executable,
            str(script),
            str(evidence_path),
        ],
        cwd=consumer,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )


def positive(consumer, env, label, path):
    result = run_replay(
        consumer, env, label, path
    )

    require(
        result.returncode == 0,
        f"{label}: standalone replay failed:\n"
        + result.stderr[-1500:],
    )

    report = json.loads(result.stdout)
    expected = CASES[label]

    require(
        report["schema"] == "VALID",
        f"{label}: invalid schema result",
    )

    require(
        report["classification_replay"] == "MATCH",
        f"{label}: replay did not match",
    )

    require(
        report["comparison"] == expected["verdict"],
        f"{label}: unexpected verdict",
    )

    for stage in ("before", "after"):
        require(
            report[stage]["status"] == expected[stage],
            f"{label}: unexpected {stage} status",
        )

    require(
        report["execution_provenance"] == "UNAUTHENTICATED",
        f"{label}: unsupported provenance claim",
    )

    print(
        f"PASS | {label.upper()} standalone replay: "
        f"{report['comparison']}",
        flush=True,
    )


def negative(consumer, env, label, original, mutation):
    document = json.loads(original.read_text())
    mutation(document)

    destination = (
        consumer / "evidence-files"
        / f"{label}-mutated.json"
    )

    destination.write_text(
        json.dumps(document, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = run_replay(
        consumer, env, label, destination
    )

    require(
        result.returncode != 0,
        f"{label}: mutated evidence was accepted",
    )

    print(
        f"PASS | {label.upper()} forged evidence rejected",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--direct", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--waiting", type=Path, required=True)

    args = parser.parse_args()

    originals = {
        name: getattr(args, name).resolve()
        for name in CASES
    }

    for label, path in originals.items():
        require(
            path.is_file(),
            f"Missing {label} evidence: {path}",
        )

    with tempfile.TemporaryDirectory(
        prefix="sentinel-c4-external-"
    ) as directory:
        base = Path(directory).resolve()

        require(
            not base.is_relative_to(ROOT),
            "Consumer is inside source repository",
        )

        consumer, copied = prepare_consumer(
            base, originals
        )

        env = isolated_environment(base)

        print(
            "PASS | Consumer isolated outside repository",
            flush=True,
        )

        print(
            "PASS | No Solidity source, Foundry or RPC",
            flush=True,
        )

        for label, path in copied.items():
            positive(consumer, env, label, path)

        negative(
            consumer,
            env,
            "direct",
            copied["direct"],
            lambda d: d["comparison"].update(
                verdict="STILL_SATISFIED"
            ),
        )

        negative(
            consumer,
            env,
            "ready",
            copied["ready"],
            lambda d: d["scenario"]["derived"].update(
                operationId="0x" + "00" * 32
            ),
        )

        negative(
            consumer,
            env,
            "waiting",
            copied["waiting"],
            lambda d: d["stages"]["before"][
                "observation"
            ].update(returnData="0xdeadbeef"),
        )

    print()
    print("EXTERNAL COMPARISON REPRODUCTION: PASS")


if __name__ == "__main__":
    main()
