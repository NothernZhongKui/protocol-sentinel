#!/usr/bin/env python3
"""Independent solc replay of published Foundry build-info.

Compares normalized contracts and sources, not compiler diagnostics.
Does not authenticate the original EVM execution.
"""

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

from build_provenance import (
    canonical,
    invalid_constant,
    read_json,
    sha256,
    unique_pairs,
)

VERSION = "0.8.24"
COMMIT = "e11b9ed9"

INPUT_KEYS = {
    "language",
    "sources",
    "settings",
    "allowPaths",
    "basePath",
    "includePaths",
    "version",
}


class BuildReplayError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise BuildReplayError(message)


def compiler_binary():
    home = Path.home()

    candidates = [
        home / "Library/Application Support/svm"
        / VERSION / f"solc-{VERSION}",
        home / ".svm" / VERSION / f"solc-{VERSION}",
        home / ".svm" / VERSION / "solc",
        home / ".local/share/svm"
        / VERSION / f"solc-{VERSION}",
    ]

    installed = shutil.which("solc")
    if installed:
        candidates.append(Path(installed))

    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue

        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if (
            result.returncode == 0
            and re.search(
                rf"\b{VERSION}\+commit\.{COMMIT}\b",
                result.stdout,
            )
        ):
            return str(path), result.stdout

    raise BuildReplayError(
        f"Exact solc {VERSION}+commit.{COMMIT} not found"
    )


def normalize_ast(value):
    if isinstance(value, list):
        return [normalize_ast(item) for item in value]

    if not isinstance(value, dict):
        return value

    return {
        key: normalize_ast(item)
        for key, item in value.items()
        if not (
            key == "nodes"
            and item == []
            and isinstance(value.get("nodeType"), str)
        )
    }


def normalize(output):
    require(
        isinstance(output, dict)
        and isinstance(output.get("contracts"), dict)
        and bool(output["contracts"]),
        "Missing contract output",
    )

    require(
        isinstance(output.get("sources"), dict)
        and bool(output["sources"]),
        "Missing source output",
    )

    data = copy.deepcopy({
        "contracts": output["contracts"],
        "sources": output["sources"],
    })

    for contracts in data["contracts"].values():
        for contract in contracts.values():
            if "abi" in contract:
                require(
                    isinstance(contract["abi"], list),
                    "Invalid ABI",
                )

                contract["abi"] = sorted(
                    contract["abi"],
                    key=canonical,
                )

            for key in ("devdoc", "userdoc"):
                if contract.get(key) == {}:
                    del contract[key]

            evm = contract.get("evm", {})

            if evm.get("methodIdentifiers") == {}:
                del evm["methodIdentifiers"]

            deployed = evm.get("deployedBytecode", {})

            if deployed.get("immutableReferences") == {}:
                del deployed["immutableReferences"]

    for source in data["sources"].values():
        if "ast" in source:
            source["ast"] = normalize_ast(source["ast"])

    return data


def verify_outputs(recorded, repeated):
    original = normalize(recorded)
    fresh = normalize(repeated)

    for section in ("contracts", "sources"):
        require(
            canonical(original[section])
            == canonical(fresh[section]),
            f"{section.upper()} MISMATCH",
        )

    return sum(
        len(contracts)
        for contracts in original["contracts"].values()
    )


def verify_input_hash(info, unit):
    require(
        sha256(canonical(info["input"]))
        == unit["compilerInputSha256"],
        "Compiler input SHA-256 mismatch",
    )


def standard_input(info):
    require(
        info.get("solcVersion", "").split("+")[0]
        == VERSION,
        "Compiler version mismatch",
    )

    saved = info["input"]

    require(
        not (set(saved) - INPUT_KEYS),
        f"Unknown compiler fields: {set(saved) - INPUT_KEYS}",
    )

    require(
        saved.get("language") == "Solidity",
        "Wrong compiler language",
    )

    require(
        isinstance(saved.get("sources"), dict)
        and bool(saved["sources"])
        and all(
            isinstance(source, dict)
            and isinstance(source.get("content"), str)
            and "urls" not in source
            for source in saved["sources"].values()
        ),
        "Compiler input lacks embedded sources",
    )

    require(
        isinstance(saved.get("settings"), dict),
        "Missing compiler settings",
    )

    return {
        key: saved[key]
        for key in ("language", "sources", "settings")
    }


def compile_info(info, binary, version):
    long_version = info.get("solcLongVersion")

    if long_version:
        require(
            long_version in version,
            "Compiler build mismatch",
        )

    result = subprocess.run(
        [binary, "--standard-json"],
        input=canonical(standard_input(info)),
        capture_output=True,
        timeout=240,
    )

    require(
        result.returncode == 0,
        f"solc process failed: {result.stderr[-800:]!r}",
    )

    output = result.stdout.decode("utf-8-sig")

    # Some solc environments prepend an SMT diagnostic.
    if output.startswith(">>>"):
        require(
            "\n" in output,
            "Malformed solc diagnostic prefix",
        )
        output = output.split("\n", 1)[1]

    try:
        repeated = json.loads(
            output,
            object_pairs_hook=unique_pairs,
            parse_constant=invalid_constant,
        )
    except (ValueError, TypeError) as exc:
        raise BuildReplayError(
            "Invalid solc JSON response"
        ) from exc

    require(
        isinstance(repeated, dict),
        "Invalid compiler response",
    )

    errors = [
        item for item in repeated.get("errors", [])
        if item.get("severity") == "error"
    ]

    require(
        not errors,
        f"Solidity compilation errors: {errors[:2]}",
    )

    return repeated


def verify_build_units(bundle):
    bundle = Path(bundle)

    manifest = read_json(
        bundle / "build-provenance.json"
    )

    units = manifest.get("units")

    require(
        isinstance(units, list) and bool(units),
        "No compiler build units",
    )

    binary, version = compiler_binary()
    total = 0

    for unit in units:
        filename = unit["file"]

        require(
            isinstance(filename, str)
            and re.fullmatch(
                r"build-info/[^/]+\.json",
                filename,
            ),
            "Unsafe build-info path",
        )

        path = bundle / filename

        require(
            path.is_file(),
            "Missing compiler build-info",
        )

        require(
            sha256(path.read_bytes())
            == unit["buildInfoSha256"],
            "Build-info SHA-256 mismatch",
        )

        info = read_json(path)
        verify_input_hash(info, unit)

        repeated = compile_info(
            info, binary, version
        )

        count = verify_outputs(
            info["output"], repeated
        )

        require(
            count > 0,
            "No compiled contracts",
        )

        total += 1

        print(
            f"PASS | {path.name} | "
            f"{count} contracts reproduced",
            flush=True,
        )

    return total


def inject_build_output_mutation(bundle):
    """Negative control; use only inside unpublished staging."""

    bundle = Path(bundle)
    manifest = read_json(
        bundle / "build-provenance.json"
    )

    path = bundle / manifest["units"][0]["file"]
    info = read_json(path)

    for contracts in info["output"]["contracts"].values():
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

                path.write_bytes(canonical(info) + b"\n")
                return

    raise BuildReplayError(
        "No bytecode available for fault injection"
    )
