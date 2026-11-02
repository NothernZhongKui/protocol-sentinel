#!/usr/bin/env python3
"""Capture and verify compiler build-info from a fresh Forge run.

Records build inputs. Does not authenticate EVM execution.
"""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

DEPENDENCIES = (
    "lib/forge-std",
    "lib/openzeppelin-contracts",
    "lib/openzeppelin-contracts-upgradeable",
)

FORMAT = "protocol-sentinel-build-provenance-v1"


class BuildProvenanceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise BuildProvenanceError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def unique_pairs(pairs):
    result = {}

    for key, value in pairs:
        require(
            key not in result,
            f"Duplicate JSON key: {key}",
        )
        result[key] = value

    return result


def invalid_constant(value):
    raise BuildProvenanceError(
        f"Invalid JSON constant: {value}"
    )


def read_json(path):
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_pairs,
        parse_constant=invalid_constant,
    )


def git(root, *args):
    return subprocess.check_output(
        ["git", *args],
        cwd=root,
        text=True,
        stderr=subprocess.PIPE,
    ).strip()


def dependencies(root):
    entries = []

    for name in DEPENDENCIES:
        path = root / name

        require(
            path.is_dir(),
            f"Missing dependency: {name}",
        )

        head = git(path, "rev-parse", "HEAD")
        index = git(
            root, "ls-files", "--stage", "--", name
        )
        fields = index.split()

        require(
            len(fields) == 4
            and fields[0] == "160000"
            and fields[1] == head
            and fields[3] == name,
            f"Dependency gitlink mismatch: {name}",
        )

        require(
            not git(
                path,
                "status",
                "--porcelain",
                "--untracked-files=all",
            ),
            f"Dirty dependency: {name}",
        )

        entries.append({
            "path": name,
            "revision": head,
        })

    return entries


def validated_input(info, root, producer_source):
    require(
        isinstance(info, dict),
        "Invalid build-info object",
    )

    require(
        isinstance(info.get("solcVersion"), str),
        "Missing solc version",
    )

    data = info.get("input")

    require(
        isinstance(data, dict),
        "Missing compiler input",
    )

    require(
        data.get("language") == "Solidity",
        "Not Solidity input",
    )

    settings = data.get("settings")
    sources = data.get("sources")

    require(
        isinstance(settings, dict),
        "Missing compiler settings",
    )

    require(
        isinstance(sources, dict) and sources,
        "Missing compiler sources",
    )

    producer_seen = False

    for name, source in sources.items():
        require(
            isinstance(name, str),
            "Invalid source name",
        )

        path = Path(name)

        require(
            not path.is_absolute()
            and ".." not in path.parts,
            f"Unsafe compiler source path: {name}",
        )

        require(
            isinstance(source, dict),
            f"Invalid source: {name}",
        )

        content = source.get("content")

        require(
            isinstance(content, str),
            f"No source content: {name}",
        )

        local = (root / path).resolve()

        require(
            local.is_relative_to(root.resolve()),
            f"External source: {name}",
        )

        require(
            local.is_file(),
            f"Source missing: {name}",
        )

        require(
            local.read_bytes() == content.encode("utf-8"),
            f"Compiler source differs from checkout: {name}",
        )

        producer_seen |= name == producer_source

    return data, producer_seen


def normalized_settings(data):
    settings = data["settings"]

    return {
        name: settings.get(name)
        for name in (
            "optimizer",
            "viaIR",
            "evmVersion",
            "metadata",
            "remappings",
            "libraries",
        )
    }


def inspect_info(path, root, producer_source):
    raw = path.read_bytes()
    info = read_json(path)

    data, producer_seen = validated_input(
        info, root, producer_source
    )

    return {
        "file": f"build-info/{path.name}",
        "buildInfoSha256": sha256(raw),
        "compilerInputSha256": sha256(canonical(data)),
        "solcVersion": info["solcVersion"],
        "sourceCount": len(data["sources"]),
        "settings": normalized_settings(data),
    }, producer_seen


def verify_bundle(directory, root, run_id, producer_source):
    manifest = read_json(
        directory / "build-provenance.json"
    )

    require(
        isinstance(manifest, dict),
        "Invalid build provenance",
    )

    require(
        manifest.get("format") == FORMAT,
        "Build format mismatch",
    )

    require(
        manifest.get("runId") == run_id,
        "Build run identity mismatch",
    )

    require(
        manifest.get("producerSource") == producer_source,
        "Build producer source mismatch",
    )

    require(
        manifest.get("dependencies") == dependencies(root),
        "Dependency revision mismatch",
    )

    units = manifest.get("units")

    require(
        isinstance(units, list) and units,
        "Missing build units",
    )

    require(
        len(units) == len({
            unit["file"] for unit in units
        }),
        "Duplicate build unit",
    )

    require(
        {
            p.name
            for p in (directory / "build-info").glob("*.json")
        } == {
            Path(unit["file"]).name for unit in units
        },
        "Build-info file set mismatch",
    )

    found_producer = False

    for unit in units:
        filename = unit["file"]

        require(
            isinstance(filename, str)
            and re.fullmatch(
                r"build-info/[^/]+\.json",
                filename,
            ) is not None,
            "Unsafe build-info path",
        )

        actual, seen = inspect_info(
            directory / filename,
            root,
            producer_source,
        )

        require(
            actual == unit,
            f"Build-info mismatch: {filename}",
        )

        found_producer |= seen

    require(
        found_producer,
        "Producer source absent from build-info",
    )

    return sha256(
        (directory / "build-provenance.json").read_bytes()
    )


def capture_bundle(
    build_info_dir,
    directory,
    root,
    run_id,
    producer_source,
):
    require(
        re.fullmatch(r"[0-9a-f]{32}", run_id) is not None,
        "Invalid build run ID",
    )

    require(
        (root / producer_source).is_file(),
        "Missing producer source",
    )

    files = sorted(build_info_dir.glob("*.json"))

    require(
        files,
        "Fresh build-info files missing",
    )

    require(
        not directory.exists(),
        "Build bundle destination exists",
    )

    deps = dependencies(root)

    (directory / "build-info").mkdir(parents=True)

    units = []

    for path in files:
        dest = directory / "build-info" / path.name

        shutil.copyfile(path, dest)

        unit, _ = inspect_info(
            dest, root, producer_source
        )

        units.append(unit)

    manifest = {
        "format": FORMAT,
        "runId": run_id,
        "producerSource": producer_source,
        "dependencies": deps,
        "units": units,
    }

    (
        directory / "build-provenance.json"
    ).write_bytes(canonical(manifest) + b"\n")

    return verify_bundle(
        directory, root, run_id, producer_source
    )


BUILD_MANIFEST_PATH = "build/build-provenance.json"


def reproduction_command(manifest, base_command):
    """Render essential effective compiler settings for a new run."""

    units = manifest["units"]

    settings = [
        {
            "optimizer": unit["settings"]["optimizer"],
            "viaIR": unit["settings"].get("viaIR"),
            "evmVersion": unit["settings"].get("evmVersion"),
        }
        for unit in units
    ]

    require(
        len({canonical(item) for item in settings}) == 1,
        "Mixed compiler settings cannot use one reproduction command",
    )

    config = settings[0]
    optimizer = config["optimizer"]

    require(
        isinstance(optimizer, dict)
        and type(optimizer.get("enabled")) is bool
        and type(optimizer.get("runs")) is int
        and optimizer["runs"] >= 0,
        "Invalid optimizer configuration",
    )

    flags = [
        "FOUNDRY_OPTIMIZER=" +
        ("true" if optimizer["enabled"] else "false"),
        f"FOUNDRY_OPTIMIZER_RUNS={optimizer['runs']}",
    ]

    via_ir = config["viaIR"]

    if via_ir is not None:
        require(type(via_ir) is bool, "Invalid viaIR")
        flags.append(
            "FOUNDRY_VIA_IR=" +
            ("true" if via_ir else "false")
        )

    evm = config["evmVersion"]

    if evm is not None:
        require(
            isinstance(evm, str)
            and re.fullmatch(r"[a-zA-Z0-9_-]+", evm),
            "Invalid EVM version",
        )
        flags.append(f"FOUNDRY_EVM_VERSION={evm}")

    return " ".join([*flags, base_command])


def verify_evidence_build(
    document,
    bundle,
    root,
    run_id,
    producer_source,
    base_command,
):
    """Verify local build bundle and its Evidence hash binding."""

    provenance = document["provenance"]
    record = provenance.get("buildProvenance")

    require(
        isinstance(record, dict),
        "Evidence missing build provenance",
    )

    require(
        record.get("format") == FORMAT
        and record.get("manifestPath") == BUILD_MANIFEST_PATH,
        "Invalid Evidence build reference",
    )

    digest = verify_bundle(
        bundle, root, run_id, producer_source
    )

    require(
        record.get("manifestSha256") == digest,
        "Evidence build manifest hash mismatch",
    )

    manifest = read_json(bundle / "build-provenance.json")

    versions = {
        unit["solcVersion"] for unit in manifest["units"]
    }

    declared_version = document["environment"]["solcVersion"]

    require(
        len(versions) == 1 and all(
            version == declared_version
            or version.startswith(declared_version + "+")
            for version in versions
        ),
        "Declared compiler version differs from build-info",
    )

    dependency_map = {
        item["path"]: item["revision"]
        for item in manifest["dependencies"]
    }

    declared_deps = document["environment"]["dependencyRevisions"]

    for name, path in (
        ("openzeppelinContracts", "lib/openzeppelin-contracts"),
        (
            "openzeppelinContractsUpgradeable",
            "lib/openzeppelin-contracts-upgradeable",
        ),
    ):
        require(
            declared_deps[name] == dependency_map[path],
            f"Evidence dependency mismatch: {name}",
        )

    require(
        provenance["runId"] == run_id,
        "Evidence/build run ID mismatch",
    )

    require(
        provenance["reproduceCommand"]
        == reproduction_command(manifest, base_command),
        "Reproduce command differs from compiler settings",
    )

    return digest


def attach_evidence_build(
    document,
    bundle,
    root,
    run_id,
    producer_source,
    base_command,
):
    provenance = document["provenance"]

    require(
        "buildProvenance" not in provenance,
        "Evidence already has build provenance",
    )

    digest = verify_bundle(
        bundle, root, run_id, producer_source
    )

    manifest = read_json(bundle / "build-provenance.json")

    provenance["buildProvenance"] = {
        "format": FORMAT,
        "manifestPath": BUILD_MANIFEST_PATH,
        "manifestSha256": digest,
    }

    provenance["reproduceCommand"] = reproduction_command(
        manifest, base_command
    )

    verify_evidence_build(
        document,
        bundle,
        root,
        run_id,
        producer_source,
        base_command,
    )

    return digest
