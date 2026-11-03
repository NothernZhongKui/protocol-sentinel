#!/usr/bin/env python3
"""Trusted policy, identity binding and decision controls."""

import copy
import tempfile
from pathlib import Path

from trusted_direct_gate import (
    GateError,
    evaluate_gate,
    read_trusted_policy,
)


def reject(label, function):
    try:
        function()
    except GateError as exc:
        print(f"PASS | {label}: {exc}")
    else:
        raise AssertionError(f"Accepted invalid case: {label}")


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        consumer = root / "consumer"
        trusted_dir = root / "trusted"

        consumer.mkdir()
        trusted_dir.mkdir()

        path = trusted_dir / "policy.toml"
        scenario_id = "0x" + "ab" * 32

        content = f'''
[policy]
version = "1"
repository = "local/consumer"
workflow = ".github/workflows/sentinel-gate.yml"

[[required_scenario]]
id = "treasury_safe"
scenario_id = "{scenario_id}"
route = "DIRECT_EOA_UUPS"
source = "test/TreasuryAuthority.t.sol"
contract = "TreasuryAuthorityTest"
test = "test_SafeUpgradePreservesRestriction"
fixture_id = "external-treasury-safe"
'''

        path.write_text(content)

        context = {
            "GITHUB_REPOSITORY": "local/consumer",
            "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "101",
            "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_WORKFLOW_REF": (
                "local/consumer/.github/workflows/"
                "sentinel-gate.yml@refs/heads/main"
            ),
        }

        trusted = read_trusted_policy(
            path, consumer, context
        )

        producer = {
            key: value
            for key, value in trusted["scenario"].items()
            if key != "route"
        }

        stage = {"status": "PASS", "reason": "NONE"}

        document = {
            "route": "DIRECT_EOA_UUPS",
            "scenario": {"scenarioId": scenario_id},
            "environment": {
                "fixtureId": "external-treasury-safe",
            },
            "provenance": {
                "repository": "consumer",
                "sourceCommit": "a" * 40,
                "runId": "b" * 32,
            },
            "comparison": {
                "verdict": "STILL_SATISFIED",
            },
            "stages": {
                "before": {"evaluation": dict(stage)},
                "after": {"evaluation": dict(stage)},
            },
        }

        report = {
            "schema": "VALID",
            "classification_replay": "MATCH",
            "comparison": "STILL_SATISFIED",
            "before": dict(stage),
            "after": dict(stage),
        }

        def decide(doc=document, rep=report, config=producer):
            return evaluate_gate(
                trusted,
                config,
                doc,
                rep,
                checkout="a" * 40,
                run_id="b" * 32,
                tool_revision="c" * 40,
            )

        assert decide()["decision"] == "PASS"
        print("PASS | Verified safe -> PASS")

        unsafe_doc = copy.deepcopy(document)
        unsafe_report = copy.deepcopy(report)

        unsafe_doc["comparison"]["verdict"] = (
            "CHANGED_TO_VIOLATION"
        )
        unsafe_doc["stages"]["after"]["evaluation"]["status"] = (
            "FAIL"
        )

        unsafe_report["comparison"] = "CHANGED_TO_VIOLATION"
        unsafe_report["after"]["status"] = "FAIL"

        assert decide(
            unsafe_doc, unsafe_report
        )["decision"] == "BLOCK"

        print("PASS | Verified unsafe -> BLOCK")

        unsafe_report["ci_decision"] = "PASS"

        assert decide(
            unsafe_doc, unsafe_report
        )["decision"] == "BLOCK"

        print("PASS | Forged PASS claim has no effect")

        mismatch = copy.deepcopy(document)
        mismatch["provenance"]["sourceCommit"] = "d" * 40

        reject(
            "Wrong checkout",
            lambda: decide(mismatch),
        )

        mismatch = copy.deepcopy(document)
        mismatch["provenance"]["runId"] = "d" * 32

        reject(
            "Wrong producer run",
            lambda: decide(mismatch),
        )

        mismatch = copy.deepcopy(document)
        mismatch["scenario"]["scenarioId"] = "0x" + "cd" * 32

        reject(
            "Replaced scenario",
            lambda: decide(mismatch),
        )

        mismatch_report = dict(report)
        mismatch_report["classification_replay"] = "MISMATCH"

        reject(
            "Replay mismatch",
            lambda: decide(document, mismatch_report),
        )

        wrong_producer = dict(producer)
        wrong_producer["test"] = "test_Other"

        reject(
            "Replaced producer",
            lambda: decide(
                document, report, wrong_producer
            ),
        )

        local_policy = consumer / "candidate-policy.toml"
        local_policy.write_text(content)

        reject(
            "Consumer-controlled policy location",
            lambda: read_trusted_policy(
                local_policy, consumer, context
            ),
        )

        wrong_context = dict(context)
        wrong_context["GITHUB_WORKFLOW_REF"] = (
            "local/consumer/.github/workflows/"
            "other.yml@refs/heads/main"
        )

        reject(
            "Wrong workflow",
            lambda: read_trusted_policy(
                path, consumer, wrong_context
            ),
        )

        path.write_text(content + """
[[required_scenario]]
id = "extra"
scenario_id = "0x""" + "cd" * 32 + """"
route = "DIRECT_EOA_UUPS"
source = "test/Other.t.sol"
contract = "OtherTest"
test = "test_Other"
fixture_id = "extra"
""")

        reject(
            "Unsupported multi-scenario gate",
            lambda: read_trusted_policy(
                path, consumer, context
            ),
        )

    print()
    print("=== TRUSTED GATE UNIT CONTROLS PASSED ===")


if __name__ == "__main__":
    main()
