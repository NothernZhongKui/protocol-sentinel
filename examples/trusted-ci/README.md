# Protected Direct UUPS GitHub CI example

**Status:** reviewable example for the v1.0 adoption milestone, **not a production-verified required workflow**. The [trusted CI guide](../../docs/guides/ci.md), [ADR-007](../../docs/adr-007-v1-developer-adoption.md) and [v0.6 runner reference](../../docs/reference/workspace-v0.6.md) remain authoritative.

## Files and intended ownership

| File | Consumer destination | Trust |
| --- | --- | --- |
| [sentinel-gate.yml](sentinel-gate.yml) | `.github/workflows/sentinel-gate.yml` | Workflow; protected against unreviewed changes |
| [prepare.py](prepare.py) | `.github/sentinel/prepare.py` | **Executed from the protected base checkout**, never the candidate checkout |
| [trusted-policy.template.toml](trusted-policy.template.toml) | `.github/sentinel/trusted-policy.toml` | Reviewed base policy with approved tool SHA and scenario |

Adapt the exact paths, project workspace, dependency list and workflow identity to your own repository **before** activating the workflow. The reference assumes a **root Foundry workspace** with the Sentinel submodule at `lib/protocol-sentinel`. Both the producer test and its fixture must be reviewed and committed. Configure the exact matching solc executable for the runner as the repository Actions variable `SENTINEL_SOLC_PATH` (absolute path on the runner), and install that compiler in your approved runner/toolchain provisioning. A fresh GitHub-hosted runner does not automatically have that path merely because a variable was set.

The template deliberately uses `YOUR_ORG/YOUR_REPO`, an all-zero **approved tool SHA**, a placeholder scenario and a placeholder fixture ID. Replace them with reviewed values. The **consumer commit remains all zeros in the protected template**: `prepare.py` replaces that one field with the SHA of the **actual tested pull-request merge checkout** in an outside-workspace per-run policy v2 file.

## Security invariants

1. A standard `pull_request` job checks out the exact event `github.sha` merge commit (never a moving pull-request ref) with read-only permissions and no persisted credentials; it does not use privileged `pull_request_target` secrets.
2. The workflow separately checks out the protected base SHA containing its **trusted** prepare script and policy. Protected config must be clean.
3. **Before executing any Python from the candidate Sentinel checkout**, the base script verifies Gitlink mode `160000`, the exact approved tool commit, actual initialized tool HEAD, the event's exact `GITHUB_SHA` and PR workflow ref, and clean tool/consumer checkout. It refuses mismatches and never copies the candidate's policy into trusted storage.
4. The protected scenario/workspace/tool/repository fields cannot be changed by the PR. Only `policy.consumer_commit` is populated from the tested checkout.
5. The trusted runner handles fresh producer execution, Git source closure, independent compiler/classification replay and `PASS / BLOCK / REVIEW`. The Job Summary only displays output from the current attempt, even if older PASS Evidence is on disk.
6. The final step propagates the runner's exit code, including `2` for verified BLOCK or an execution error and `3` for REVIEW.

**Required GitHub protection is external.** A candidate may modify the workflow and retain its job name while replacing the body with `exit 0`. Required status-check names **alone do not close that bypass**. Configure a ruleset / branch protection requiring this check, enforce reviewed workflow changes (for example CODEOWNERS with required owner approval, or centrally controlled required workflows), and enforce owner review for producer, fixture, policy and tool-pin changes. The correct configuration must be tested with a non-bypass actor; do not assume a repository maintainer who can bypass protections represents ordinary contributors.

## Pilot acceptance (not yet claimed)

Use a separate actual consumer repository and create **four non-merged pull requests**: a safe implementation (verified MATCH and PASS), a test-only faulty migration (MATCH and BLOCK), a candidate PR replacing the required job body with `exit 0`, and a candidate PR changing the Sentinel gitlink. Verify merge is prevented where appropriate, including after check-name spoofing. Test a fifth case where a previous PASS bundle exists but the current producer fails; the summary must say VERIFICATION FAILED and the CI job must not be green.

Record the exact tested consumer SHA, permitted tool SHA, workflow run IDs/attempts, ruleset requirements and verification result. This example alone cannot establish independent merge enforcement or EVM execution authenticity.

## Local tests

```bash
python3.12 -B examples/trusted-ci/test_prepare.py
```

The tests create temporary Git repositories and locally pinned fake Sentinel submodules; they test the **pre-Sentinel trust boundary** only, not the complete Foundry producer or GitHub ruleset behavior.
