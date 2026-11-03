#!/usr/bin/env python3
"""Trusted CI bridge for freshly verified Direct Evidence.

The caller must select the policy and CI context from a protected
workflow. A file outside the consumer is not itself an attestation.
"""

import hashlib
import re
import tomllib
from pathlib import Path

from ci_policy import aggregate

SHA = re.compile(r"[0-9a-f]{40}\Z")
SCENARIO = re.compile(r"0x[0-9a-fA-F]{64}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")

FIELDS = {
    "id",
    "scenario_id",
    "route",
    "source",
    "contract",
    "test",
    "fixture_id",
}

CI_VARS = (
    "GITHUB_REPOSITORY",
    "GITHUB_SHA",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_ATTEMPT",
    "GITHUB_WORKFLOW_REF",
)


class GateError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise GateError(reason)


def read_trusted_policy(path, project, environ):
    """Load a single-scenario policy outside the consumer checkout."""

    project = Path(project).resolve()
    path = Path(path)

    require(path.is_absolute(), "POLICY_PATH_NOT_ABSOLUTE")

    path = path.resolve()

    require(
        not path.is_relative_to(project) and path.is_file(),
        "UNTRUSTED_POLICY_LOCATION",
    )

    content = path.read_bytes()
    data = tomllib.loads(content.decode("utf-8"))

    require(
        set(data) == {"policy", "required_scenario"},
        "INVALID_POLICY_SECTIONS",
    )

    policy = data["policy"]

    require(
        isinstance(policy, dict)
        and set(policy) == {"version", "repository", "workflow"}
        and policy["version"] == "1",
        "UNSUPPORTED_POLICY",
    )

    repository = policy["repository"]
    workflow = policy["workflow"]

    require(
        isinstance(repository, str)
        and REPO.fullmatch(repository) is not None,
        "INVALID_POLICY_REPOSITORY",
    )

    require(
        isinstance(workflow, str)
        and workflow.startswith(".github/workflows/")
        and workflow.endswith((".yml", ".yaml"))
        and ".." not in Path(workflow).parts,
        "INVALID_TRUSTED_WORKFLOW",
    )

    scenarios = data["required_scenario"]

    require(
        isinstance(scenarios, list) and len(scenarios) == 1,
        "ONE_REQUIRED_SCENARIO_PER_RUN",
    )

    scenario = scenarios[0]

    require(
        isinstance(scenario, dict)
        and set(scenario) == FIELDS
        and all(
            isinstance(value, str) and bool(value)
            for value in scenario.values()
        ),
        "INVALID_REQUIRED_SCENARIO",
    )

    require(
        scenario["route"] == "DIRECT_EOA_UUPS"
        and SCENARIO.fullmatch(
            scenario["scenario_id"]
        ) is not None,
        "UNSUPPORTED_REQUIRED_SCENARIO",
    )

    context = {name: environ.get(name) for name in CI_VARS}

    require(
        all(
            isinstance(value, str) and bool(value)
            for value in context.values()
        ),
        "MISSING_TRUSTED_CI_CONTEXT",
    )

    require(
        context["GITHUB_REPOSITORY"] == repository
        and project.name == repository.split("/")[-1],
        "CI_REPOSITORY_MISMATCH",
    )

    require(
        SHA.fullmatch(context["GITHUB_SHA"]) is not None,
        "INVALID_CI_CHECKOUT",
    )

    require(
        all(
            value.isdecimal()
            and 0 < int(value)
            and len(value) <= 20
            for value in (
                context["GITHUB_RUN_ID"],
                context["GITHUB_RUN_ATTEMPT"],
            )
        ),
        "INVALID_CI_EXECUTION_ID",
    )

    workflow_prefix = repository + "/" + workflow + "@"

    require(
        context["GITHUB_WORKFLOW_REF"].startswith(
            workflow_prefix
        )
        and len(context["GITHUB_WORKFLOW_REF"])
        > len(workflow_prefix),
        "CI_WORKFLOW_MISMATCH",
    )

    return {
        "policy": policy,
        "scenario": scenario,
        "context": context,
        "policy_sha256": hashlib.sha256(content).hexdigest(),
    }


def evaluate_gate(
    trusted,
    producer,
    document,
    replay_report,
    *,
    checkout,
    run_id,
    tool_revision,
):
    """Decide only after the caller has verified fresh Evidence."""

    scenario = trusted["scenario"]
    context = trusted["context"]
    provenance = document["provenance"]

    require(
        checkout == context["GITHUB_SHA"]
        and provenance["sourceCommit"] == checkout,
        "CHECKOUT_REVISION_MISMATCH",
    )

    require(
        provenance["runId"] == run_id,
        "SENTINEL_RUN_ID_MISMATCH",
    )

    require(
        provenance["repository"]
        == trusted["policy"]["repository"].split("/")[-1],
        "EVIDENCE_REPOSITORY_MISMATCH",
    )

    require(
        document["route"] == scenario["route"]
        and document["environment"]["fixtureId"]
        == scenario["fixture_id"],
        "SCENARIO_ROUTE_OR_FIXTURE_MISMATCH",
    )

    require(
        int(document["scenario"]["scenarioId"], 16)
        == int(scenario["scenario_id"], 16),
        "SCENARIO_ID_MISMATCH",
    )

    for name in (
        "id",
        "scenario_id",
        "source",
        "contract",
        "test",
        "fixture_id",
    ):
        require(
            producer[name] == scenario[name],
            "TRUSTED_PRODUCER_MISMATCH",
        )

    require(
        replay_report["schema"] == "VALID"
        and replay_report["classification_replay"] == "MATCH",
        "INDEPENDENT_REPLAY_NOT_VERIFIED",
    )

    require(
        document["comparison"]["verdict"]
        == replay_report["comparison"],
        "COMPARISON_REPLAY_MISMATCH",
    )

    for stage in ("before", "after"):
        require(
            document["stages"][stage]["evaluation"]
            == replay_report[stage],
            "STAGE_REPLAY_MISMATCH",
        )

    decision = aggregate(
        [scenario["id"]],
        [{
            "id": producer["id"],
            "verdict": replay_report["comparison"],
        }],
    )

    return {
        "format": "protocol-sentinel-ci-gate-v1",
        "policy_version": trusted["policy"]["version"],
        "policy_sha256": trusted["policy_sha256"],
        "ci_context": context,
        "sentinel_run_id": run_id,
        "tool_revision": tool_revision,
        "verification": "FRESH_VERIFIED_DIRECT_EVIDENCE",
        "evidence": "evidence.json",
        **decision,
    }
