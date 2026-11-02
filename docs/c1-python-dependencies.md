# Comparison Evidence C1 — Python Dependencies

Python is not required to use the Solidity helper library.

Independent comparison evidence validation and replay
use Python 3.12 in CI.

Direct dependencies are version-pinned in:

- evidence/requirements-schema.txt
- evidence/requirements-abi.txt

Installation:

    python3.12 -m pip install \
      -r evidence/requirements-schema.txt \
      -r evidence/requirements-abi.txt

C1 does not claim cryptographic reproducibility
of Python package acquisition.

Transitive hash locking is deferred. This is a
documented implementation deviation from the
dependency-locking goal of ADR-004C, not a change
to the frozen Solidity classification semantics.

The required guarantees for C1 are structural
schema validation, frozen source semantics and
independent ABI/Keccak equivalence.
