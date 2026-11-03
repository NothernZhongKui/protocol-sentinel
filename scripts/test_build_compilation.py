#!/usr/bin/env python3
"""Adversarial controls for independent compiler replay."""

import argparse
import copy
from pathlib import Path

from build_provenance import (
    read_json,
)
from replay_build_compilation import (
    BuildReplayError,
    compile_info,
    compiler_binary,
    normalize,
    verify_build_units,
    verify_input_hash,
    verify_outputs,
)


def reject(action, label):
    try:
        action()
    except BuildReplayError:
        print(f"PASS | Rejected {label}")
    else:
        raise AssertionError(
            f"Accepted mutation: {label}"
        )


def change_abi(output):
    for contracts in output["contracts"].values():
        for contract in contracts.values():
            abi = contract.get("abi", [])

            if abi:
                abi[0]["type"] = "__MUTATED__"
                return

    raise AssertionError("Missing ABI mutation target")


def change_ast(output):
    for source in output["sources"].values():
        ast = source.get("ast")

        if isinstance(ast, dict):
            ast["id"] = ast["id"] + 1
            return

    raise AssertionError("Missing AST mutation target")


def change_bytecode(output):
    for contracts in output["contracts"].values():
        for contract in contracts.values():
            bytecode = (
                contract.get("evm", {})
                .get("bytecode", {})
                .get("object")
            )

            if isinstance(bytecode, str) and bytecode:
                contract["evm"]["bytecode"]["object"] = (
                    ("0" if bytecode[0] != "0" else "1")
                    + bytecode[1:]
                )
                return

    raise AssertionError("Missing bytecode mutation target")


def change_metadata(output):
    for contracts in output["contracts"].values():
        for contract in contracts.values():
            metadata = contract.get("metadata")

            if isinstance(metadata, str):
                contract["metadata"] = metadata + " "
                return

    raise AssertionError("Missing metadata mutation target")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "completed",
        type=Path,
    )

    args = parser.parse_args()

    runs = [
        path for path in args.completed.iterdir()
        if path.is_dir()
    ]

    assert runs, "No completed runs"

    directory = max(
        runs,
        key=lambda path: (
            path.stat().st_mtime_ns,
            path.name,
        ),
    )

    bundle = directory / "build"

    total = verify_build_units(bundle)

    assert total > 0

    manifest = read_json(
        bundle / "build-provenance.json"
    )

    unit = manifest["units"][0]
    info = read_json(
        bundle / unit["file"]
    )

    binary, version = compiler_binary()

    repeated = compile_info(
        info, binary, version
    )

    verify_outputs(
        info["output"], repeated
    )

    for label, mutate in (
        ("ABI", change_abi),
        ("AST", change_ast),
        ("bytecode", change_bytecode),
        ("metadata", change_metadata),
    ):
        forged = copy.deepcopy(info["output"])
        mutate(forged)

        reject(
            lambda output=forged: verify_outputs(
                output, repeated
            ),
            label,
        )

    forged_info = copy.deepcopy(info)

    optimizer = forged_info["input"][
        "settings"
    ].setdefault("optimizer", {})

    optimizer["runs"] = (
        optimizer.get("runs", 200) + 1
    )

    reject(
        lambda: verify_input_hash(
            forged_info, unit
        ),
        "compiler optimizer settings",
    )

    print(
        "STEP 296: BUILD REPLAY MUTATIONS PASS"
    )


if __name__ == "__main__":
    main()
