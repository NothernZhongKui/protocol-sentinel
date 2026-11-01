import json
import subprocess
from pathlib import Path

PATH = Path("artifacts/demo/authority-regression.json")

if not PATH.is_file():
    raise SystemExit("ERROR: Witness file not found")

data = json.loads(PATH.read_text())
failures = []


def check(name, condition):
    passed = bool(condition)
    print(f'{"PASS" if passed else "FAIL"} | {name}')
    if not passed:
        failures.append(name)


def is_hex(value, size):
    return (
        isinstance(value, str)
        and value.startswith("0x")
        and len(value) == 2 + size * 2
        and all(c in "0123456789abcdefABCDEF" for c in value[2:])
    )


required = [
    "policy_id", "policy_rule", "result",
    "actor", "target", "calldata", "call_success",
    "implementation_before", "implementation_after",
    "minimum_delay", "timestamp_before", "timestamp_after",
    "timelock_operation_id", "timelock_scheduled_at",
    "timelock_ready_at", "timelock_executed_at",
    "source_commit", "proxy_codehash",
    "implementation_before_codehash",
    "implementation_after_codehash"
]

missing = [key for key in required if key not in data]

if missing:
    raise SystemExit(f"ERROR: Missing fields: {missing}")

check("Policy AR-001", data["policy_id"] == "AR-001")
check(
    "Expected policy rule",
    data["policy_rule"] == "NO_IMPLEMENTATION_REPLACEMENT"
)
check("Regression detected", data["result"] == "FAIL")
check("Call succeeded", data["call_success"] is True)

# Verify exact ABI call format.
calldata = data["calldata"]

if not is_hex(calldata, 100):
    raise SystemExit("ERROR: Invalid calldata format")

raw = bytes.fromhex(calldata[2:])

selector = subprocess.check_output(
    ["cast", "sig", "upgradeToAndCall(address,bytes)"],
    text=True
).strip()

check("Correct function selector", raw[:4].hex() == selector[2:].lower())

requested = int.from_bytes(raw[4:36], "big")
offset = int.from_bytes(raw[36:68], "big")
payload_length = int.from_bytes(raw[68:100], "big")

check("Valid ABI address", requested < 2**160)
check("Valid ABI offset", offset == 64)
check("Empty upgrade calldata", payload_length == 0)

before = int(data["implementation_before"], 16)
after = int(data["implementation_after"], 16)

check("Valid implementation addresses", before < 2**160 and after < 2**160)
check("Implementation changed", before != after)
check("Requested implementation installed", after == requested)

# Verify observed time relationships.
scheduled = int(data["timelock_scheduled_at"])
ready = int(data["timelock_ready_at"])
executed = int(data["timelock_executed_at"])
delay = int(data["minimum_delay"])

check("Timelock operation ID", is_hex(data["timelock_operation_id"], 32))
check("Positive timelock delay", delay > 0)
check("Scheduled delay respected", ready - scheduled == delay)
check("Execution not premature", executed >= ready)
check(
    "No time advancement during direct call",
    data["timestamp_before"] == data["timestamp_after"]
)
check(
    "Direct call after authorized upgrade",
    data["timestamp_before"] >= executed
)

# Source and bytecode provenance.
head = subprocess.check_output(
    ["git", "rev-parse", "HEAD"],
    text=True
).strip()

check("Source commit matches HEAD", data["source_commit"] == head)

zero_hash = "0x" + "00" * 32

for field in [
    "proxy_codehash",
    "implementation_before_codehash",
    "implementation_after_codehash"
]:
    check(
        f"Valid {field}",
        is_hex(data[field], 32) and data[field].lower() != zero_hash
    )

check(
    "Implementation code changed",
    data["implementation_before_codehash"]
    != data["implementation_after_codehash"]
)

print()

if failures:
    raise SystemExit(f"FAILED: {len(failures)} checks")

print("Protocol Sentinel witness verification PASSED")
