#!/usr/bin/env python3
"""Trusted external workspace gate positive and adversarial controls."""

import copy
import tempfile
from pathlib import Path

from trusted_workspace_gate import (
    WorkspaceGateError, read_workspace_policy, evaluate_workspace_gate
)
from workspace_context import WorkspaceContext


def reject(label, action, reason):
    try:
        action()
    except WorkspaceGateError as exc:
        assert reason in str(exc), (label, str(exc))
        print(f"PASS | Rejected {label}: {exc}")
    else:
        raise AssertionError(f"Accepted {label}")


def main():
    with tempfile.TemporaryDirectory(prefix="sentinel-gate-v2-") as tmp:
        base = Path(tmp)
        root = base / "consumer"
        project = root / "projects/capu"
        tool = project / "lib/protocol-sentinel"
        tool.mkdir(parents=True)
        trusted_dir = base / "trusted"
        trusted_dir.mkdir()
        context = WorkspaceContext(
            repository_root=root,
            project_root=project,
            tool_root=tool,
            workspace="projects/capu",
            tool_path="projects/capu/lib/protocol-sentinel",
            repository_commit="a" * 40,
            tool_commit="c" * 40,
        )
        scenario_id = "0x" + "ab" * 32
        policy = trusted_dir / "policy.toml"
        policy.write_text(f"""
[policy]
version = "2"
repository = "NothernZhongKui/protocol-sentinel"
consumer_repository = "Capminal/capminal-contracts"
consumer_commit = "{'a' * 40}"
workspace = "projects/capu"
workflow = ".github/workflows/test.yml"
tool_commit = "{'c' * 40}"

[[required_scenario]]
id = "capu_safe"
scenario_id = "{scenario_id}"
route = "DIRECT_EOA_UUPS"
source = "test/CapuSentinelProducer.t.sol"
contract = "CapuSentinelProducerTest"
test = "test_ProduceSafe"
fixture_id = "capu-v0.6-safe"
""")
        env = {
            "GITHUB_REPOSITORY": "NothernZhongKui/protocol-sentinel",
            "GITHUB_SHA": "b" * 40,
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW_REF": (
                "NothernZhongKui/protocol-sentinel/"
                ".github/workflows/test.yml@refs/heads/main"
            ),
        }
        trusted = read_workspace_policy(policy, context, env)
        producer = {
            key: value for key, value in trusted["scenario"].items()
            if key != "route"
        }
        stage = {"status": "PASS", "reason": "NONE"}
        doc = {
            "route": "DIRECT_EOA_UUPS",
            "environment": {"fixtureId": producer["fixture_id"]},
            "scenario": {"scenarioId": scenario_id},
            "provenance": {
                "repository": "Capminal/capminal-contracts",
                "sourceCommit": context.repository_commit,
                "toolCommit": context.tool_commit,
                "workspace": context.workspace,
                "runId": "d" * 32,
            },
            "stages": {
                "before": {"evaluation": dict(stage)},
                "after": {"evaluation": dict(stage)},
            },
            "comparison": {"verdict": "STILL_SATISFIED"},
        }
        report = {
            "schema": "VALID",
            "classification_replay": "MATCH",
            "comparison": "STILL_SATISFIED",
            "before": dict(stage),
            "after": dict(stage),
        }

        def evaluate(document=doc, result=report, candidate=producer):
            return evaluate_workspace_gate(
                trusted, context, candidate, document, result, "d" * 32
            )

        assert evaluate()["decision"] == "PASS"
        print("PASS | Safe independent replay -> CI PASS")
        unsafe = copy.deepcopy(doc)
        unsafe_report = copy.deepcopy(report)
        unsafe["comparison"]["verdict"] = "CHANGED_TO_VIOLATION"
        unsafe_report["comparison"] = "CHANGED_TO_VIOLATION"
        unsafe["stages"]["after"]["evaluation"]["status"] = "FAIL"
        unsafe_report["after"]["status"] = "FAIL"
        assert evaluate(unsafe, unsafe_report)["decision"] == "BLOCK"
        print("PASS | Matching regression replay -> CI BLOCK")
        swapped = copy.deepcopy(doc)
        swapped["provenance"]["workspace"] = "projects/other"
        reject(
            "cross-workspace Evidence",
            lambda: evaluate(swapped),
            "EVIDENCE_IDENTITY_MISMATCH",
        )
        swapped = copy.deepcopy(doc)
        swapped["provenance"]["repository"] = "renamed-local-folder"
        reject(
            "consumer repo substitution",
            lambda: evaluate(swapped),
            "EVIDENCE_REPOSITORY_MISMATCH",
        )
        swapped = copy.deepcopy(report)
        swapped["classification_replay"] = "MISMATCH"
        reject(
            "forged classification replay",
            lambda: evaluate(doc, swapped),
            "INDEPENDENT_REPLAY_NOT_VERIFIED",
        )

        bad = policy.read_text().replace("projects/capu", "projects/other", 1)
        policy.write_text(bad)
        reject(
            "trusted workspace mismatch",
            lambda: read_workspace_policy(policy, context, env),
            "TRUSTED_WORKSPACE_MISMATCH",
        )
        policy.write_text(bad.replace("projects/other", "projects/capu", 1))
        bad = policy.read_text().replace(
            'consumer_commit = "' + "a" * 40 + '"',
            'consumer_commit = "' + "e" * 40 + '"',
        )
        policy.write_text(bad)
        reject(
            "untrusted consumer SHA",
            lambda: read_workspace_policy(policy, context, env),
            "TRUSTED_CONSUMER_COMMIT_MISMATCH",
        )

    print("=== TRUSTED WORKSPACE GATE CONTROLS PASSED ===")


if __name__ == "__main__":
    main()
