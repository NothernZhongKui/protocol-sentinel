#!/usr/bin/env python3
"""Synthetic and adversarial build provenance tests."""

import json
import tempfile
from pathlib import Path

from build_provenance import (
    BuildProvenanceError,
    capture_bundle,
    read_json,
    verify_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "a" * 32
PRODUCER = "test/DirectComparisonEvidenceCapture.t.sol"


def reject(fn, label):
    try:
        fn()
    except (
        BuildProvenanceError,
        ValueError,
        FileNotFoundError,
    ):
        print(f"PASS | Rejected {label}")
    else:
        raise AssertionError(f"Accepted {label}")


def write_info(path, runs=321):
    data = {
        "solcVersion": "0.8.24",
        "input": {
            "language": "Solidity",
            "sources": {
                PRODUCER: {
                    "content": (ROOT / PRODUCER).read_text(),
                },
            },
            "settings": {
                "optimizer": {
                    "enabled": True,
                    "runs": runs,
                },
                "evmVersion": "cancun",
            },
        },
    }

    path.write_text(
        json.dumps(data), encoding="utf-8"
    )


def main():
    with tempfile.TemporaryDirectory(
        prefix="sentinel-build-provenance-"
    ) as temp:
        base = Path(temp)

        build = base / "fresh"
        build.mkdir()

        info = build / "compiler.json"
        write_info(info)

        bundle = base / "published"

        digest = capture_bundle(
            build, bundle, ROOT, RUN_ID, PRODUCER
        )

        assert digest == verify_bundle(
            bundle, ROOT, RUN_ID, PRODUCER
        )

        print(
            "PASS | Build provenance capture and verification"
        )

        reject(
            lambda: verify_bundle(
                bundle, ROOT, "b" * 32, PRODUCER
            ),
            "different run identity",
        )

        copied = bundle / "build-info/compiler.json"
        original = copied.read_bytes()

        write_info(copied, runs=999)

        reject(
            lambda: verify_bundle(
                bundle, ROOT, RUN_ID, PRODUCER
            ),
            "compiler settings tampering",
        )

        copied.write_bytes(original)

        assert verify_bundle(
            bundle, ROOT, RUN_ID, PRODUCER
        ) == digest

        tampered = read_json(copied)

        tampered["input"]["sources"][PRODUCER][
            "content"
        ] += "\n// forged"

        copied.write_text(
            json.dumps(tampered),
            encoding="utf-8",
        )

        reject(
            lambda: verify_bundle(
                bundle, ROOT, RUN_ID, PRODUCER
            ),
            "compiler source tampering",
        )

        copied.write_bytes(original)

        manifest_path = (
            bundle / "build-provenance.json"
        )

        original_manifest = manifest_path.read_bytes()
        manifest = read_json(manifest_path)

        manifest["dependencies"][0]["revision"] = (
            "0" * 40
        )

        manifest_path.write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )

        reject(
            lambda: verify_bundle(
                bundle, ROOT, RUN_ID, PRODUCER
            ),
            "dependency revision tampering",
        )

        manifest_path.write_bytes(original_manifest)

        empty = base / "empty"
        empty.mkdir()

        reject(
            lambda: capture_bundle(
                empty,
                base / "absent",
                ROOT,
                RUN_ID,
                PRODUCER,
            ),
            "missing fresh build-info",
        )

    print(
        "STEP 290: BUILD PROVENANCE FOUNDATION PASS"
    )


if __name__ == "__main__":
    main()
