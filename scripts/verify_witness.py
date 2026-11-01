import json
from pathlib import Path

path = Path("artifacts/demo/authority-regression.json")
data = json.loads(path.read_text())

before = int(data["implementation_before"], 16)
after = int(data["implementation_after"], 16)
calldata = data["calldata"]

# First ABI argument: the proposed implementation address.
requested = int(calldata[10:74], 16) if len(calldata) >= 74 else -1

checks = {
    "Policy is AR-001": data["policy_id"] == "AR-001",
    "Regression detected": data["result"] == "FAIL",
    "Call succeeded": data["call_success"] is True,
    "Implementation changed": before != after,
    "Requested implementation installed": after == requested,
    "No time advancement": (
        data["timestamp_before"] == data["timestamp_after"]
    ),
    "Timelock delay unchanged": data["minimum_delay"] == 172800,
}

for name, passed in checks.items():
    print(f'{"PASS" if passed else "FAIL"} | {name}')

if not all(checks.values()):
    raise SystemExit("Witness verification failed")

print("\nAuthority Regression witness verified.")
