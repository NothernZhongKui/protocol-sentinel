#!/usr/bin/env python3
"""Trusted v0.6 workspace gate. Classification MATCH is not merge PASS."""

import hashlib
import re
import tomllib
from pathlib import Path

from ci_policy import aggregate
from trusted_direct_gate import FIELDS, CI_VARS, SCENARIO, REPO, SHA


class WorkspaceGateError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise WorkspaceGateError(reason)


def read_workspace_policy(path, context, environ):
    raw = Path(path)
    require(raw.is_absolute(), "POLICY_PATH_NOT_ABSOLUTE")
    path = raw.resolve()
    require(
        path.is_file() and not path.is_relative_to(context.repository_root),
        "UNTRUSTED_POLICY_LOCATION",
    )
    content = path.read_bytes()
    data = tomllib.loads(content.decode("utf-8"))
    require(set(data) == {"policy", "required_scenario"}, "INVALID_POLICY_SECTIONS")
    policy = data["policy"]
    require(
        isinstance(policy, dict)
        and set(policy) == {
            "version", "repository", "consumer_repository",
            "consumer_commit", "workspace", "workflow", "tool_commit"
        }
        and policy["version"] == "2",
        "UNSUPPORTED_WORKSPACE_POLICY",
    )
    require(
        REPO.fullmatch(policy["repository"]) is not None,
        "INVALID_POLICY_REPOSITORY",
    )
    require(
        isinstance(policy["consumer_repository"], str)
        and REPO.fullmatch(policy["consumer_repository"]) is not None,
        "INVALID_CONSUMER_REPOSITORY",
    )
    require(
        isinstance(policy["consumer_commit"], str)
        and SHA.fullmatch(policy["consumer_commit"]) is not None
        and policy["consumer_commit"] == context.repository_commit,
        "TRUSTED_CONSUMER_COMMIT_MISMATCH",
    )
    require(
        policy["workspace"] == context.workspace,
        "TRUSTED_WORKSPACE_MISMATCH",
    )
    require(
        isinstance(policy["tool_commit"], str)
        and SHA.fullmatch(policy["tool_commit"]) is not None
        and policy["tool_commit"] == context.tool_commit,
        "TRUSTED_TOOL_REVISION_MISMATCH",
    )
    workflow = policy["workflow"]
    require(
        isinstance(workflow, str)
        and workflow.startswith(".github/workflows/")
        and workflow.endswith((".yml", ".yaml"))
        and ".." not in Path(workflow).parts,
        "INVALID_TRUSTED_WORKFLOW",
    )
    scenarios = data["required_scenario"]
    require(
        isinstance(scenarios, list) and len(scenarios) == 1
        and isinstance(scenarios[0], dict)
        and set(scenarios[0]) == FIELDS
        and all(isinstance(v, str) and v for v in scenarios[0].values()),
        "ONE_REQUIRED_SCENARIO_PER_RUN",
    )
    scenario = scenarios[0]
    require(
        scenario["route"] == "DIRECT_EOA_UUPS"
        and SCENARIO.fullmatch(scenario["scenario_id"]) is not None,
        "UNSUPPORTED_REQUIRED_SCENARIO",
    )
    ci = {name: environ.get(name) for name in CI_VARS}
    require(
        all(isinstance(v, str) and v for v in ci.values()),
        "MISSING_TRUSTED_CI_CONTEXT",
    )
    require(
        ci["GITHUB_REPOSITORY"] == policy["repository"]
        and isinstance(ci["GITHUB_SHA"], str)
        and SHA.fullmatch(ci["GITHUB_SHA"]) is not None,
        "CI_CHECKOUT_MISMATCH",
    )
    require(
        ci["GITHUB_WORKFLOW_REF"].startswith(
            policy["repository"] + "/" + workflow + "@"
        ),
        "CI_WORKFLOW_MISMATCH",
    )
    require(
        all(
            v.isdecimal() and 0 < int(v) and len(v) <= 20
            for v in (ci["GITHUB_RUN_ID"], ci["GITHUB_RUN_ATTEMPT"])
        ),
        "INVALID_CI_EXECUTION_ID",
    )
    return {
        "policy": policy,
        "scenario": scenario,
        "context": ci,
        "policy_sha256": hashlib.sha256(content).hexdigest(),
    }


def evaluate_workspace_gate(trusted, context, producer, evidence, report, run_id):
    policy = trusted["policy"]
    scenario = trusted["scenario"]
    provenance = evidence["provenance"]
    require(
        provenance["sourceCommit"] == context.repository_commit
        and provenance["toolCommit"] == context.tool_commit
        and provenance["workspace"] == context.workspace
        and provenance["runId"] == run_id,
        "EVIDENCE_IDENTITY_MISMATCH",
    )
    require(
        provenance["repository"] == policy["consumer_repository"],
        "EVIDENCE_REPOSITORY_MISMATCH",
    )
    require(
        evidence["route"] == scenario["route"]
        and evidence["environment"]["fixtureId"] == scenario["fixture_id"]
        and int(evidence["scenario"]["scenarioId"], 16)
        == int(scenario["scenario_id"], 16),
        "SCENARIO_IDENTITY_MISMATCH",
    )
    for name in ("id", "scenario_id", "source", "contract", "test", "fixture_id"):
        require(producer[name] == scenario[name], "TRUSTED_PRODUCER_MISMATCH")
    require(
        report["schema"] == "VALID"
        and report["classification_replay"] == "MATCH"
        and report["comparison"] == evidence["comparison"]["verdict"],
        "INDEPENDENT_REPLAY_NOT_VERIFIED",
    )
    for stage in ("before", "after"):
        require(
            report[stage] == evidence["stages"][stage]["evaluation"],
            "STAGE_REPLAY_MISMATCH",
        )
    decision = aggregate(
        [scenario["id"]],
        [{"id": producer["id"], "verdict": report["comparison"]}],
    )
    return {
        "format": "protocol-sentinel-ci-gate-v2",
        "policy_version": "2",
        "policy_sha256": trusted["policy_sha256"],
        "ci_context": trusted["context"],
        "workspace": context.workspace,
        "tool_revision": context.tool_commit,
        "sentinel_run_id": run_id,
        "verification": "FRESH_VERIFIED_WORKSPACE_EVIDENCE",
        "evidence": "evidence.json",
        **decision,
    }
