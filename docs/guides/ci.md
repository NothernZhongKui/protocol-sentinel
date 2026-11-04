# Trusted CI for Direct comparisons

A local runner can validate and publish evidence without deciding whether a change should merge. A trusted CI policy adds `PASS`, `BLOCK` or `REVIEW` for one declared Direct scenario per invocation. A classification replay `MATCH` alone is not approval.

## Establish the boundary

1. Write a producer that captures the actual comparison and completes even if it reports a violation. Put expected-verdict assertions in separate tests.
2. Select a pinned Sentinel verifier and the required scenario from protected configuration. Select policy from a trusted base or other protected source, place it outside the consumer checkout, and pass its absolute path using `--trusted-policy`.
3. Protect the workflow, policy, verifier revision and required checks against unreviewed changes. Review changes to the scenario, fixture and producer; a valid replay cannot prove that a deliberately weakened test covers the intended property.
4. Make branch rules require the actual trusted check. A file outside the checkout, a matching workflow name or a green job alone does not prevent a PR from replacing a workflow.

For the **v0.6 workspace runner**, policy v2 separately binds the workflow repository and workflow context, consumer repository and exact consumer commit, workspace, tool commit and one required producer. The gate reads GitHub environment values; those values are only as trustworthy as the workflow and execution environment that supplies them. See the [policy and context reference](../reference/workspace-v0.6.md#trusted-policy). The [Capminal acceptance harness](../../scripts/check_capu_workspace.sh) demonstrates binding and negative controls; its local synthetic context is for testing, not a production trust boundary.

For **v0.5**, see the [reference consumer gate](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/1f1eb1799b8cfd01e6506bf477eb94fff7f1afbb/.github/workflows/sentinel-gate.yml), [integrity workflow](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/1f1eb1799b8cfd01e6506bf477eb94fff7f1afbb/.github/workflows/sentinel-integrity.yml) and [policy](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/1f1eb1799b8cfd01e6506bf477eb94fff7f1afbb/.github/sentinel/trusted-policy.toml). Adapt identity, permissions and required checks to your repository; enforce them with repository rules.

## Enforce the check on pull requests

Run the candidate checkout with the exact pinned Sentinel submodule and matching solc. Select the trusted policy from the protected base revision or another source not controlled by the candidate, place it outside the candidate checkout, and bind it to the tested consumer commit. The policy, verifier revision, required scenario and workflow must not be chosen by unreviewed PR code. Publish diagnostics even when the gate exits `2` or `3`.

Configure branch protection or a repository ruleset to **require** the authority gate and any separate integrity check. Confirm with a deliberately unsafe test PR that `CHANGED_TO_VIOLATION` yields `BLOCK` and a failed required check. A failed Actions job by itself is not proof that a merge is prevented. Review changes to producer and fixtures separately: a valid replay cannot establish that an intentionally weakened scenario still protects the intended invariant.

## Interpret outcomes

| Verified comparison | Decision |
| --- | --- |
| `STILL_SATISFIED` | `PASS` |
| `CHANGED_TO_VIOLATION`, `STILL_VIOLATED` | `BLOCK` |
| `CHANGED_TO_SATISFIED`, `INDETERMINATE`, `INCOMPARABLE` | `REVIEW` |

A missing, failed, skipped or ambiguous required producer, invalid evidence or failed verification blocks. Trusted runner exit codes are `0` for PASS, `2` for BLOCK or error, `3` for REVIEW. A verified BLOCK may still produce a completed evidence bundle. See [results](../reference/results.md).
