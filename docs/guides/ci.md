# Trusted CI for Portable Direct

The local runner verifies and publishes evidence but does not make a merge decision. A trusted CI policy adds that decision for one declared Direct producer per run.

1. Configure a producer that records the observed comparison without asserting that it is safe. Put expected safe or unsafe verdict assertions in separate tests.
2. Select the policy from a trusted base revision and place it outside the consumer checkout. Pass its absolute path using `--trusted-policy`.
3. Pin the Sentinel verifier revision in a protected workflow and bind the expected repository, workflow and producer in the policy.
4. Protect the required workflow, policy, dependency pin and required checks against unreviewed changes. Review scenario and fixture changes as well.
5. Inspect the gate decision and evidence. `MATCH` alone is not approval; see [results](../reference/results.md).

The gate validates GitHub CI context, checkout revision and producer identity. A file outside the checkout, a matching workflow name, or a green job by itself does not establish that the workflow cannot be replaced by the PR.

The [reference consumer's gate](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/1f1eb1799b8cfd01e6506bf477eb94fff7f1afbb/.github/workflows/sentinel-gate.yml), [integrity workflow](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/1f1eb1799b8cfd01e6506bf477eb94fff7f1afbb/.github/workflows/sentinel-integrity.yml), and [policy](https://github.com/NothernZhongKui/protocol-sentinel-consumer/blob/1f1eb1799b8cfd01e6506bf477eb94fff7f1afbb/.github/sentinel/trusted-policy.toml) show one integration. Adapt repository identity, paths, pinned version, permissions and required checks to your own repository; the repository rules must actually enforce those checks.

A producer that fails, is skipped, is ambiguous or fails verification cannot produce a valid gate PASS. Trusted policy mode returns exit codes `0` (PASS), `2` (BLOCK or error), and `3` (REVIEW). Details: [configuration](../reference/configuration.md) and [ADR-005B](../adr-005b-trusted-ci-gate.md).
