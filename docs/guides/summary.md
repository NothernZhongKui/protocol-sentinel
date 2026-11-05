# Trusted workspace GitHub Summary

The v1.0.0 Summary is a display renderer, not an Evidence verifier or CI gate.

The renderer accepts the completed run directory from the **current** workspace invocation. It does not scan previous Evidence directories. When the current producer fails before publication, omit --run-dir and the output will say **VERIFICATION FAILED**, even if previous successful bundles remain on disk.

Invoke the renderer after the workspace runner, passing its real exit status, repository, GitHub SHA, run ID and attempt, and GITHUB_STEP_SUMMARY. Extract the current completed path only from this invocation's COMPLETED output. Never select the most recent directory under artifacts.

The renderer validates consistency of the current run's recorded output for display; it does not reproduce compiler outputs, authenticate EVM execution, or choose a merge policy. The protected CI workflow must independently check the candidate tool gitlink against the approved base SHA **before invoking Sentinel Python**, construct per-run policy v2 with the tested consumer checkout SHA and preserve the runner's exit code (0 PASS, 2 BLOCK/error, 3 REVIEW).

For integration guidance see [trusted CI](ci.md) and [ADR-007](../adr-007-v1-developer-adoption.md). An Actions Summary is not a required GitHub merge rule.

The stale-Evidence regression test asserts: a previous PASS exists, the current producer fails, the Summary reports VERIFICATION FAILED, and the runner exit remains nonzero. This is distinct from GitHub branch-rule enforcement.
