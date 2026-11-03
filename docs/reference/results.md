# Results and decisions

These levels answer different questions; `PASS` at one level is not a substitute for a CI decision.

| Level | Values | Question |
| --- | --- | --- |
| Single-stage policy | `PASS`, `FAIL`, `UNKNOWN` | Does this observation satisfy the declared policy? |
| Comparison | See table below | What changed between the stages? |
| Classification replay | `MATCH` on successful replay | Does Python reproduce the recorded classification? |
| Trusted CI policy | `PASS`, `BLOCK`, `REVIEW` | What decision does the configured gate make? |

## Direct stage policies

| Observation | `NO_IMPLEMENTATION_REPLACEMENT` | `NO_SUCCESSFUL_UPGRADE_CALL` |
| --- | --- | --- |
| Expected rejection, valid candidate, implementation unchanged | `PASS` | `PASS` |
| Successful replacement | `FAIL` | `FAIL` |
| Successful call, implementation unchanged | `UNKNOWN` | `FAIL` |
| Unexpected revert or invalid/missing required evidence | `UNKNOWN` | `UNKNOWN` |

The expected revert is supplied by the test author; matching bytes do not establish which branch caused the rejection. `ERROR` is reserved for setup or execution failures and is not a separate emitted policy verdict. Details and diagnostic reasons: [library guide](../library-quickstart.md).

## Comparison and trusted policy

| Before | After | Comparison | CI decision |
| --- | --- | --- | --- |
| `PASS` | `PASS` | `STILL_SATISFIED` | `PASS` |
| `PASS` | `FAIL` | `CHANGED_TO_VIOLATION` | `BLOCK` |
| `FAIL` | `FAIL` | `STILL_VIOLATED` | `BLOCK` |
| `FAIL` | `PASS` | `CHANGED_TO_SATISFIED` | `REVIEW` |
| `UNKNOWN` | Any valid status, or vice versa | `INDETERMINATE` | `REVIEW` |
| Incompatible stages | | `INCOMPARABLE` | `REVIEW` |

Stage identity and comparability checks can take precedence over the status combinations. Missing, invalid, or mismatched required scenarios block the trusted gate. A local run without a trusted policy reports `NOT_EVALUATED`, even when replay matches.

For example, `MATCH` + `CHANGED_TO_VIOLATION` means the violation was reproduced from the recorded evidence. In trusted CI it maps to `BLOCK`. Neither replay nor a matching revert authenticates execution; see the [threat model](../threat-model.md).
