#!/usr/bin/env python3
"""Generate a test-only authorization regression from pinned Fortytwo source."""

import subprocess
import sys
from pathlib import Path

EXPECTED_COMMIT = "2ee48d0af7dfdc6f0daa0a3017b70edf137033ec"

if len(sys.argv) != 4 or sys.argv[3] not in ("--write", "--check"):
    raise SystemExit(
        "Usage: generate_risky_fixture.py SOURCE OUTPUT --write|--check"
    )

source = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()

root = source.parent.parent

head = subprocess.check_output(
    ["git", "-C", str(root), "rev-parse", "HEAD"],
    text=True,
).strip()

assert head == EXPECTED_COMMIT, "Unexpected Fortytwo source commit"

subprocess.run(
    ["git", "-C", str(root), "diff", "--exit-code",
     "HEAD", "--", "src/X402Escrow.sol"],
    check=True,
)

original = source.read_text()

old_name = "contract X402Escrow is"
old_auth = (
    "function _authorizeUpgrade(address) "
    "internal override onlyOwner {}"
)

new_auth = """function _authorizeUpgrade(address) internal override {
        if (
            msg.sender != owner()
            && !hasRole(FACILITATOR_ROLE, msg.sender)
        ) {
            revert OwnableUnauthorizedAccount(msg.sender);
        }
    }"""

assert original.count(old_name) == 1
assert original.count(old_auth) == 1

generated = original.replace(
    old_name, "contract LocalX402EscrowRisky is", 1
).replace(old_auth, new_auth, 1)

if sys.argv[3] == "--write":
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated)
else:
    assert output.is_file(), "Existing fixture missing"
    assert output.read_text() == generated, (
        "Existing risky fixture differs from generated source"
    )

print("PASS | Pinned external source verified")
print("PASS | Risky fixture generated deterministically")
print("PASS | Existing test fixture matches generated source")
print("PASS | Original Fortytwo source unchanged")
