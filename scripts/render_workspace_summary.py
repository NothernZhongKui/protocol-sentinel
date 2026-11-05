#!/usr/bin/env python3
"""Display-only GitHub Job Summary for one *current* trusted v0.6 workspace run.

This renderer is not a verifier, classifier or CI gate. Its result must never
replace the workspace runner's exit code. It never discovers previous bundles.
"""

import argparse
import json
import re
import sys
from pathlib import Path

RUN_ID = re.compile(r"[0-9a-f]{32}\Z")
EXPECTED_EXIT = {"PASS": 0, "BLOCK": 2, "REVIEW": 3}


def _display(value):
    # GitHub Markdown values are presentation only, never trusted HTML.
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text.replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")[:160]


def _load(run_dir, filename):
    path = run_dir / filename
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Missing or invalid " + filename)
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _table_row(key, value):
    return f"| {_display(key)} | {_display(value)} |"


def render(run_dir, runner_exit, *, repository, sha, github_run_id, attempt):
    """Return Markdown for current execution; error state is not a policy verdict."""
    heading = ["## Protocol Sentinel — Authority Gate", ""]
    if run_dir is None:
        return "\n".join(heading + [
            "**VERIFICATION FAILED**",
            "",
            "No completed Evidence was published by this attempt.",
            f"Runner exit: {_display(runner_exit)}",
            "",
        ])

    try:
        root = Path(run_dir)
        _require(not root.is_symlink() and root.is_dir(), "Invalid current run directory")
        _require(RUN_ID.fullmatch(root.name) is not None, "Invalid Sentinel run identifier")
        verification = _load(root, "verification.json")
        gate = _load(root, "ci-gate.json")
        evidence = _load(root, "evidence.json")
        _require(isinstance(verification, dict) and isinstance(gate, dict)
                 and isinstance(evidence, dict), "Malformed result JSON")
        _require(verification.get("publication") == "COMPLETED", "Evidence not completed")
        _require(verification.get("schema") == "VALID", "Evidence schema not valid")
        _require(verification.get("classification_replay") == "MATCH", "Independent replay mismatch")
        _require(verification.get("build_replay") == "ISOLATED_COMPILER_OUTPUT_MATCH",
                 "Compiler output replay mismatch")
        _require(verification.get("build_provenance") == "VERIFIED_V2",
                 "Build provenance missing")
        _require(verification.get("run_id") == root.name
                 and gate.get("sentinel_run_id") == root.name
                 and evidence.get("provenance", {}).get("runId") == root.name,
                 "Evidence belongs to a different Sentinel run")
        _require(gate.get("format") == "protocol-sentinel-ci-gate-v2"
                 and gate.get("verification") == "FRESH_VERIFIED_WORKSPACE_EVIDENCE",
                 "Not a trusted verified gate report")
        decision = gate.get("decision")
        _require(decision in EXPECTED_EXIT and runner_exit == EXPECTED_EXIT[decision],
                 "Runner exit and gate decision disagree")
        _require(verification.get("ci_decision") == decision, "Verification and gate disagree")
        context = gate.get("ci_context")
        _require(isinstance(context, dict), "Missing CI context")
        required = {
            "GITHUB_REPOSITORY": repository,
            "GITHUB_SHA": sha,
            "GITHUB_RUN_ID": str(github_run_id),
            "GITHUB_RUN_ATTEMPT": str(attempt),
        }
        _require(all(context.get(k) == v for k, v in required.items()),
                 "Evidence CI context differs from the current attempt")
        verdict = verification.get("comparison")
        _require(verdict == evidence.get("comparison", {}).get("verdict"),
                 "Comparison verdict mismatch")
        before, after = verification.get("before"), verification.get("after")
        _require(isinstance(before, dict) and isinstance(after, dict),
                 "Missing before/after observations")
        stages = evidence.get("stages", {})
        _require(before == stages.get("before", {}).get("evaluation")
                 and after == stages.get("after", {}).get("evaluation"),
                 "Stage evaluations differ")
        _require(isinstance(gate.get("scenarios"), list)
                 and len(gate["scenarios"]) == 1
                 and gate["scenarios"][0].get("verdict") == verdict,
                 "Scenario verdict differs")
        scenario = gate["scenarios"][0].get("id", "<unidentified>")
        return "\n".join(heading + [
            f"**CI DECISION: {_display(decision)}**",
            "",
            "| Property | Observed result |",
            "| --- | --- |",
            _table_row("Scenario", scenario),
            _table_row("Baseline", before.get("status")),
            _table_row("Upgraded", after.get("status")),
            _table_row("Comparison", verdict),
            _table_row("Independent replay", verification.get("classification_replay")),
            _table_row("Compiler replay", "MATCH"),
            _table_row("Evidence", root.name),
            "",
            "Evidence is verified for this declared scenario only. "
            "Replay MATCH does not imply merge approval.",
            "",
        ])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return "\n".join(heading + [
            "**VERIFICATION FAILED**",
            "",
            "Current run Evidence could not be presented: " + _display(exc),
            f"Runner exit: {_display(runner_exit)}",
            "",
            "No previous completed Evidence was used.",
            "",
        ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", help="Exact completed directory from this invocation; omit on runner failure")
    parser.add_argument("--runner-exit", type=int, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--github-run-id", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--summary-path", type=Path, required=True)
    args = parser.parse_args(argv)
    markdown = render(
        args.run_dir, args.runner_exit, repository=args.repository,
        sha=args.sha, github_run_id=args.github_run_id, attempt=args.attempt,
    )
    # Display-only: do not change the actual trusted gate's exit code.
    with args.summary_path.open("a", encoding="utf-8") as stream:
        stream.write(markdown + "\n")
    print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
