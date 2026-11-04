#!/usr/bin/env python3
"""Standalone v0.6 build manifest: repository/workspace/source-bound.

This is not an Evidence writer. The v0.5 v1 manifest and its schema
remain untouched. A future v0.6 Evidence schema must explicitly name v2.
"""

import hashlib
import json
import re
import shutil
from pathlib import Path

from build_provenance import read_json, canonical
from source_closure import attest_build_sources, attest_source, git, index_entry

FORMAT_V2 = "protocol-sentinel-build-provenance-v2"
SAFE_NAME = re.compile(r"[A-Za-z0-9_.-]+\.json\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class WorkspaceProvenanceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise WorkspaceProvenanceError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def integration_inputs(context):
    # Explicit root and workspace configs, plus root submodule topology.
    # Additional inherited configs are discovered via profile extends.
    root = context.repository_root
    names = {
        "foundry.toml",
        ".gitmodules",
        (Path(context.workspace) / "foundry.toml").as_posix(),
    }
    to_scan = [root / "foundry.toml", context.project_root / "foundry.toml"]
    seen = set()
    import tomllib
    while to_scan:
        path = to_scan.pop()
        if not path.is_file() or path in seen:
            continue
        seen.add(path)
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for profile in data.get("profile", {}).values():
            if not isinstance(profile, dict):
                continue
            inherited = profile.get("extends")
            if isinstance(inherited, str) and inherited.endswith(".toml"):
                resolved = (path.parent / inherited).resolve()
                require(resolved.is_relative_to(root), "Inherited config escapes repository")
                names.add(resolved.relative_to(root).as_posix())
                to_scan.append(resolved)

    # Do not require a lockfile when all dependencies are Git-pinned.
    for path in [root / "foundry.lock", context.project_root / "foundry.lock"]:
        if path.is_file():
            names.add(path.relative_to(root).as_posix())
    for path in [root / ".gitmodules", context.project_root / ".gitmodules"]:
        if path.is_file():
            names.add(path.relative_to(root).as_posix())

    results = []
    for name in sorted(names):
        physical = (root / name).resolve()
        require(physical.is_file() and physical.is_relative_to(root), "Missing integration input")
        relative = physical.relative_to(root).as_posix()
        mode, blob = index_entry(root, relative)
        require(mode in {"100644", "100755"}, "Untracked integration config")
        raw = physical.read_bytes()
        require(
            git(root, "hash-object", "--no-filters", "--", str(physical)) == blob,
            "Integration config differs from Git index",
        )
        results.append({"path": relative, "sha256": digest(raw), "gitBlob": blob})
    return results


def unit_record(context, path, producer_source):
    require(SAFE_NAME.fullmatch(path.name) is not None, "Unsafe build-info filename")
    raw = path.read_bytes()
    info = read_json(path)
    sources = attest_build_sources(context, info)
    require(producer_source in info["input"]["sources"], "Producer absent from compiler input")
    require(info["input"].get("language") == "Solidity", "Non-Solidity compiler input")
    return {
        "file": "build-info/" + path.name,
        "sha256": digest(raw),
        "compilerInputSha256": digest(canonical({
            key: info["input"][key] for key in ("language", "sources", "settings")
        })),
        "solcVersion": info["solcVersion"],
        "sourceUnits": [
            {
                "name": source.logical_name,
                "path": source.repository_path,
                "owner": source.owner_path,
                "ownerCommit": source.owner_commit,
                "gitBlob": source.git_blob,
                "sha256": source.sha256,
                "providedInInput": source.provided_in_input,
            }
            for source in sources
        ],
    }


def expected_manifest(context, bundle, producer_source):
    require(
        isinstance(producer_source, str)
        and producer_source.startswith("test/")
        and producer_source.endswith(".sol")
        and ".." not in Path(producer_source).parts,
        "Invalid producer source identity",
    )
    attest_source(context, producer_source)
    folder = bundle / "build-info"
    files = sorted(folder.glob("*.json"))
    require(bool(files), "Missing build-info units")
    require(
        len(files) == len({p.name for p in files}),
        "Duplicate build-info units",
    )
    units = [unit_record(context, path, producer_source) for path in files]
    return {
        "format": FORMAT_V2,
        "repositoryCommit": context.repository_commit,
        "workspace": context.workspace,
        "toolPath": context.tool_path,
        "toolCommit": context.tool_commit,
        "producerSource": producer_source,
        "integrationInputs": integration_inputs(context),
        "units": units,
    }


def capture_v2(context, fresh, destination, producer_source):
    destination = Path(destination)
    require(not destination.exists(), "Build destination already exists")
    paths = sorted(Path(fresh).glob("*.json"))
    require(bool(paths), "No compiler build units")
    (destination / "build-info").mkdir(parents=True, exist_ok=False)
    try:
        for path in paths:
            require(SAFE_NAME.fullmatch(path.name) is not None, "Unsafe build file name")
            shutil.copyfile(path, destination / "build-info" / path.name)
        manifest = expected_manifest(context, destination, producer_source)
        (destination / "build-provenance.json").write_bytes(
            canonical(manifest) + b"\n"
        )
        return verify_v2(context, destination, producer_source)
    except Exception:
        shutil.rmtree(destination)
        raise


def verify_v2(context, bundle, producer_source):
    bundle = Path(bundle)
    recorded = read_json(bundle / "build-provenance.json")
    require(isinstance(recorded, dict), "Invalid v2 manifest")
    require(recorded.get("format") == FORMAT_V2, "Unsupported manifest version")
    require(
        set(recorded) == {
            "format", "repositoryCommit", "workspace",
            "toolPath", "toolCommit", "producerSource",
            "integrationInputs", "units",
        },
        "Unexpected v2 manifest fields",
    )
    require(
        recorded == expected_manifest(context, bundle, producer_source),
        "V2 manifest does not match Git-attested build",
    )
    return digest((bundle / "build-provenance.json").read_bytes())
