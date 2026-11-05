#!/usr/bin/env python3
"""Protected-base helper for one Direct UUPS trusted GitHub Actions run.

IMPORTANT: The workflow must execute THIS SCRIPT FROM A PROTECTED BASE CHECKOUT,
never from the untrusted PR checkout or its Sentinel gitlink.
"""

import argparse
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SCENARIO = re.compile(r"0x[0-9a-fA-F]{64}\Z")
POLICY_FIELDS = {
    "version", "repository", "consumer_repository", "consumer_commit",
    "workspace", "workflow", "tool_commit",
}
SCENARIO_FIELDS = {
    "id", "scenario_id", "route", "source", "contract", "test", "fixture_id",
}


class PreparationError(ValueError):
    pass


def require(condition, why):
    if not condition:
        raise PreparationError(why)


def git(directory, *args):
    result = subprocess.run(
        ["git", *args], cwd=directory, text=True, capture_output=True,
        check=False,
    )
    require(result.returncode == 0, "git failed: " + " ".join(args))
    return result.stdout.strip()


def prepare(trusted_base, consumer, policy_source, output, expected_base, environment):
    trusted_base = Path(trusted_base).resolve()
    consumer = Path(consumer).resolve()
    policy_source = Path(policy_source).resolve()
    output = Path(output).absolute()
    require(trusted_base.is_dir() and consumer.is_dir(), "Missing protected base or candidate checkout")
    require(SHA.fullmatch(expected_base) is not None, "Expected trusted base SHA must be a full SHA")
    require(git(trusted_base, "rev-parse", "HEAD") == expected_base, "Trusted base checkout SHA mismatch")
    require(policy_source.is_file() and policy_source.is_relative_to(trusted_base),
            "Policy template must come from protected base")
    require(output.is_relative_to(trusted_base) is False and
            not output.is_relative_to(consumer) and output != policy_source,
            "Generated policy must be outside protected base and candidate checkout")
    require(not output.exists() and output.parent.is_dir(), "Refuse to overwrite trusted policy output")

    data = tomllib.loads(policy_source.read_text(encoding="utf-8"))
    require(isinstance(data, dict) and set(data) == {"policy", "required_scenario"},
            "Unexpected policy template sections")
    policy = data["policy"]
    scenarios = data["required_scenario"]
    require(isinstance(policy, dict) and set(policy) == POLICY_FIELDS, "Invalid trusted policy keys")
    require(isinstance(scenarios, list) and len(scenarios) == 1
            and isinstance(scenarios[0], dict) and set(scenarios[0]) == SCENARIO_FIELDS,
            "Exactly one protected Direct UUPS scenario required")
    scenario = scenarios[0]
    require(policy["version"] == "2" and policy["consumer_commit"] == "0" * 40,
            "Template must use policy v2 and an all-zero consumer_commit placeholder")
    require(all(isinstance(policy[k], str) for k in policy), "Invalid policy field type")
    require(SHA.fullmatch(policy["tool_commit"]) is not None, "Invalid protected tool SHA")
    require(scenario["route"] == "DIRECT_EOA_UUPS" and
            isinstance(scenario["scenario_id"], str) and
            SCENARIO.fullmatch(scenario["scenario_id"]) is not None,
            "Invalid trusted scenario")
    require(all(isinstance(v, str) and v for v in scenario.values()),
            "Invalid protected scenario field")
    repository = environment.get("GITHUB_REPOSITORY", "")
    require(REPO.fullmatch(repository) is not None and
            policy["repository"] == repository and policy["consumer_repository"] == repository,
            "Protected repository identity differs from trusted GitHub context")
    workflow = policy["workflow"]
    require(workflow.startswith(".github/workflows/") and workflow.endswith((".yml", ".yaml"))
            and ".." not in Path(workflow).parts, "Invalid protected workflow path")
    workflow_ref = environment.get("GITHUB_WORKFLOW_REF", "")
    require(workflow_ref.startswith(repository + "/" + workflow + "@"),
            "Unexpected workflow identity")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        value = environment.get(key, "")
        require(value.isdecimal() and 0 < int(value) and len(value) <= 20,
                "Invalid trusted GitHub run identity: " + key)

    # Validate the exact tested candidate *before executing candidate Sentinel
    # code*. Do not derive an approved tool SHA from the PR's gitlink.
    consumer_sha = git(consumer, "rev-parse", "HEAD")
    require(SHA.fullmatch(consumer_sha) is not None, "Invalid tested consumer SHA")
    workspace = policy["workspace"]
    require(workspace == "." or (workspace and not Path(workspace).is_absolute()
            and ".." not in Path(workspace).parts), "Unsafe workspace path")
    project = consumer if workspace == "." else consumer / workspace
    require(project.is_dir() and (project / "foundry.toml").is_file(),
            "Foundry workspace not found")
    tool_relative = Path("lib/protocol-sentinel")
    tool = project / tool_relative
    require(tool.is_dir() and (tool / "scripts/run_workspace_direct.py").is_file(),
            "Sentinel gitlink missing or not initialized")
    rel = tool.relative_to(consumer).as_posix()
    metadata = git(consumer, "ls-tree", "HEAD", "--", rel).split()
    require(len(metadata) == 4 and metadata[0] == "160000"
            and metadata[2] == policy["tool_commit"] and metadata[3] == rel,
            "Candidate Sentinel gitlink not approved by protected policy")
    require(git(tool, "rev-parse", "HEAD") == policy["tool_commit"],
            "Installed Sentinel checkout not at approved SHA")
    require(not git(tool, "status", "--porcelain", "--untracked-files=all"),
            "Installed Sentinel checkout modified")
    require(not git(consumer, "status", "--porcelain", "--untracked-files=all"),
            "Consumer checkout modified before runner")

    # Preserve exact template fields. Replace only consumer_commit; this is a
    # plain TOML field with a unique full-SHA placeholder, never an expression.
    raw = policy_source.read_text(encoding="utf-8")
    placeholder = 'consumer_commit = "' + "0" * 40 + '"'
    require(raw.count(placeholder) == 1, "Expected exactly one consumer_commit placeholder")
    final = raw.replace(placeholder, 'consumer_commit = "' + consumer_sha + '"')
    parsed = tomllib.loads(final)
    require(parsed["policy"]["consumer_commit"] == consumer_sha and
            parsed["policy"]["tool_commit"] == policy["tool_commit"] and
            parsed["required_scenario"] == scenarios, "Trusted policy transformation changed protected fields")
    with output.open("x", encoding="utf-8") as handle:
        handle.write(final)
    return {"consumer_sha": consumer_sha, "tool_sha": policy["tool_commit"],
            "workspace": workspace, "policy_path": str(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trusted-base", required=True)
    parser.add_argument("--consumer", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.trusted_base, args.consumer, args.template,
                         args.output, args.base_sha, os.environ)
    except (PreparationError, OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print("TRUSTED PREFLIGHT FAILED | " + str(exc), file=sys.stderr)
        return 2
    for name, value in result.items():
        print(name.upper() + "=" + value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
