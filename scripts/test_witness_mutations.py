import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WITNESS = ROOT / "artifacts/demo/authority-regression.json"
VERIFIER = ROOT / "scripts/verify_witness.py"

baseline = json.loads(WITNESS.read_text())

def mutant(**changes):
    data = copy.deepcopy(baseline)
    data.update(changes)
    return data

cases = [
    (
        "Invalid actor and target",
        mutant(actor=None, target=[])
    ),
    (
        "Negative implementation address",
        mutant(implementation_before="-1")
    ),
    (
        "Negative Timelock timestamps",
        mutant(
            timelock_scheduled_at=-172800,
            timelock_ready_at=0,
            timelock_executed_at=0,
            timestamp_before=0,
            timestamp_after=0
        )
    ),
    (
        "Zero Timelock operation ID",
        mutant(timelock_operation_id="0x" + "00" * 32)
    ),
    (
        "Identical code hashes with different hex case",
        mutant(
            implementation_before_codehash="0x" + "ab" * 32,
            implementation_after_codehash="0x" + "AB" * 32
        )
    ),
    (
        "Unsupported schema and run kind",
        mutant(
            schema_version="999",
            run_kind="ethereum_mainnet_transaction"
        )
    ),
]

cases.append((
    "Wrong implementation slot identity",
    mutant(observed_slot="0x" + "00" * 32)
))

missing_slot = copy.deepcopy(baseline)
missing_slot.pop("observed_slot", None)
cases.append(("Missing observed slot", missing_slot))

missing = copy.deepcopy(baseline)
for field in ("schema_version", "run_kind", "fixture_id"):
    missing.pop(field, None)

cases.append(("Missing required context", missing))

with tempfile.TemporaryDirectory(
    prefix=".sentinel-f04-",
    dir=ROOT
) as temp:
    work = Path(temp)
    (work / "scripts").mkdir()
    (work / "artifacts/demo").mkdir(parents=True)

    shutil.copy2(
        VERIFIER,
        work / "scripts/verify_witness.py"
    )

    destination = work / "artifacts/demo/authority-regression.json"

    def verify(data):
        destination.write_text(json.dumps(data, indent=2))
        return subprocess.run(
            [sys.executable, "scripts/verify_witness.py"],
            cwd=work,
            capture_output=True,
            text=True
        )

    control = verify(baseline)

    if control.returncode != 0:
        print("ERROR: Original witness failed")
        print(control.stdout)
        print(control.stderr)
        sys.exit(2)

    print("PASS | Original witness accepted")
    print()

    accepted = []

    for name, data in cases:
        result = verify(data)

        if result.returncode == 0:
            print(f"RED  | Invalid witness accepted: {name}")
            accepted.append(name)
        else:
            print(f"PASS | Invalid witness rejected: {name}")

print()
print(f"Invalid witnesses accepted: {len(accepted)}/{len(cases)}")

if accepted:
    sys.exit("F04 reproduced: verifier needs stricter validation")

print("All F04 mutation tests passed")
