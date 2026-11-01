import json
import subprocess
from pathlib import Path

PATH = Path("artifacts/demo/authority-regression.json")


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL | {message}")
    print(f"PASS | {message}")


def is_hex(value, size=None):
    if not isinstance(value, str) or not value.startswith("0x"):
        return False

    digits = value[2:]

    if len(digits) % 2:
        return False

    if size is not None and len(digits) != size * 2:
        return False

    return all(c in "0123456789abcdefABCDEF" for c in digits)


def is_uint(value):
    return type(value) is int and 0 <= value < 2**256


def nonzero_hex(value):
    return int(value, 16) != 0


def unique_keys(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value

    return result


require(PATH.is_file(), "Witness exists")

try:
    data = json.loads(
        PATH.read_text(),
        object_pairs_hook=unique_keys
    )
except (ValueError, UnicodeDecodeError) as exc:
    raise SystemExit(f"FAIL | Invalid JSON: {exc}")

require(isinstance(data, dict), "JSON root is an object")

required = [
    "schema_version",
    "run_kind",
    "fixture_id",
    "policy_id",
    "policy_rule",
    "result",
    "actor",
    "target",
    "owner",
    "calldata",
    "call_success",
    "return_data",
    "observed_slot",
    "implementation_before",
    "implementation_after",
    "proxy_admin_slot",
    "minimum_delay",
    "timestamp_before",
    "timestamp_after",
    "timelock_operation_id",
    "timelock_scheduled_at",
    "timelock_ready_at",
    "timelock_executed_at",
    "source_commit",
    "proxy_codehash",
    "implementation_before_codehash",
    "implementation_after_codehash",
    "coverage",
    "reproduce",
]

require(
    all(field in data for field in required),
    "All required fields present"
)

require(data["schema_version"] == "0.1", "Supported schema")
require(data["run_kind"] == "local_fixture", "Local fixture")
require(
    data["fixture_id"] == "transparent_uups_authority_regression_v0.1",
    "Expected fixture"
)

require(data["policy_id"] == "AR-001", "Policy AR-001")
require(
    data["policy_rule"] == "NO_IMPLEMENTATION_REPLACEMENT",
    "Expected policy rule"
)
require(data["result"] == "FAIL", "Regression detected")
require(data["call_success"] is True, "Successful observed call")

# Validate address fields.
for field in ("actor", "target", "owner"):
    value = data[field]
    require(
        is_hex(value, 20) and nonzero_hex(value),
        f"Valid address: {field}"
    )

# Verify ERC-1967 implementation slot identity.
ERC1967_IMPLEMENTATION_SLOT = (
    "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
)

require(
    is_hex(data["observed_slot"], 32),
    "Valid observed slot"
)

require(
    int(data["observed_slot"], 16)
    == int(ERC1967_IMPLEMENTATION_SLOT, 16),
    "Correct ERC-1967 implementation slot"
)

# Validate storage words and implementation addresses.
for field in (
    "implementation_before",
    "implementation_after",
    "proxy_admin_slot"
):
    require(
        is_hex(data[field], 32),
        f"Valid bytes32: {field}"
    )

before = int(data["implementation_before"], 16)
after = int(data["implementation_after"], 16)

require(
    0 < before < 2**160 and 0 < after < 2**160,
    "Valid implementation addresses"
)
require(before != after, "Implementation changed")

require(
    is_hex(data["return_data"]),
    "Valid return data"
)

# Validate canonical upgradeToAndCall(address,bytes).
require(is_hex(data["calldata"], 100), "Canonical calldata length")

raw = bytes.fromhex(data["calldata"][2:])

selector = subprocess.check_output(
    ["cast", "sig", "upgradeToAndCall(address,bytes)"],
    text=True
).strip().lower()

require(
    raw[:4].hex() == selector[2:],
    "Correct function selector"
)

requested = int.from_bytes(raw[4:36], "big")
offset = int.from_bytes(raw[36:68], "big")
payload_length = int.from_bytes(raw[68:100], "big")

require(0 < requested < 2**160, "Valid candidate address")
require(offset == 64, "Canonical ABI offset")
require(payload_length == 0, "Empty initialization data")
require(after == requested, "Requested implementation installed")

# Validate unsigned timestamps and delay.
time_fields = (
    "minimum_delay",
    "timestamp_before",
    "timestamp_after",
    "timelock_scheduled_at",
    "timelock_ready_at",
    "timelock_executed_at"
)

for field in time_fields:
    require(is_uint(data[field]), f"Valid uint256: {field}")

delay = data["minimum_delay"]
scheduled = data["timelock_scheduled_at"]
ready = data["timelock_ready_at"]
executed = data["timelock_executed_at"]

require(delay > 0, "Positive timelock delay")
require(ready - scheduled == delay, "Timelock delay respected")
require(executed >= ready, "Timelock execution not premature")
require(
    data["timestamp_before"] == data["timestamp_after"],
    "No time advancement during direct call"
)
require(
    data["timestamp_before"] >= executed,
    "Direct call after authorized upgrade"
)

# Validate operation ID.
operation_id = data["timelock_operation_id"]

require(
    is_hex(operation_id, 32) and nonzero_hex(operation_id),
    "Nonzero Timelock operation ID"
)

# Validate source provenance.
head = subprocess.check_output(
    ["git", "rev-parse", "HEAD"],
    text=True
).strip()

require(
    isinstance(data["source_commit"], str)
    and data["source_commit"] == head,
    "Source commit matches HEAD"
)

# Validate code hashes as bytes, not case-sensitive strings.
hash_fields = (
    "proxy_codehash",
    "implementation_before_codehash",
    "implementation_after_codehash"
)

for field in hash_fields:
    value = data[field]
    require(
        is_hex(value, 32) and nonzero_hex(value),
        f"Valid code hash: {field}"
    )

before_hash = bytes.fromhex(
    data["implementation_before_codehash"][2:]
)
after_hash = bytes.fromhex(
    data["implementation_after_codehash"][2:]
)

require(before_hash != after_hash, "Implementation code changed")

for field in ("coverage", "reproduce"):
    require(
        isinstance(data[field], str) and bool(data[field].strip()),
        f"Valid metadata: {field}"
    )

print()
print("Protocol Sentinel witness verification PASSED")
print("Mode: internal consistency validation only")
