#!/usr/bin/env python3
"""Attest Foundry compiler source units to Git-owned checkout bytes.

Source-unit names are Solidity compiler identifiers, not trusted paths.
The caller must supply a verified WorkspaceContext.
This module does not write Evidence or authenticate EVM execution.
"""

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from workspace_context import WorkspaceContext


class SourceClosureError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SourceClosureError(message)


def git(directory, *args, binary=False):
    completed = subprocess.run(
        ["git", *args],
        cwd=directory,
        capture_output=True,
        check=False,
        text=not binary,
    )
    require(completed.returncode == 0, "Git verification failed: " + " ".join(args[:2]))
    return completed.stdout if binary else completed.stdout.strip()


def index_entry(owner, relative):
    output = git(owner, "ls-files", "--stage", "-z", "--", relative, binary=True)
    rows = [row for row in output.split(b"\0") if row]
    require(len(rows) == 1 and b"\t" in rows[0], "Source not uniquely tracked")
    metadata, name = rows[0].split(b"\t", 1)
    require(
        name.decode("utf-8", "surrogateescape") == relative,
        "Source index path differs",
    )
    parts = metadata.decode("ascii").split()
    require(len(parts) == 3 and parts[2] == "0", "Unmerged source index")
    return parts[0], parts[1]


def attest_owner(repository, physical):
    repository = repository.resolve()
    physical = physical.resolve()
    require(physical.is_relative_to(repository), "Source outside checkout")
    root = Path(git(physical.parent, "rev-parse", "--show-toplevel")).resolve()
    require(root == repository or root.is_relative_to(repository), "Unowned source")
    current = root
    owner_revision = git(root, "rev-parse", "HEAD")
    while current != repository:
        parent_text = git(current, "rev-parse", "--show-superproject-working-tree")
        require(bool(parent_text), "Unregistered source repository")
        parent = Path(parent_text).resolve()
        require(
            parent == repository or parent.is_relative_to(repository),
            "Git parent outside checkout",
        )
        relative = current.relative_to(parent).as_posix()
        mode, revision = index_entry(parent, relative)
        require(mode == "160000", "Invalid submodule entry")
        require(revision == git(current, "rev-parse", "HEAD"), "Submodule gitlink mismatch")
        require(
            not git(current, "status", "--porcelain", "--untracked-files=all"),
            "Dirty submodule owner",
        )
        current = parent
    return root, owner_revision


@dataclass(frozen=True)
class AttestedSource:
    logical_name: str
    repository_path: str
    owner_path: str
    owner_commit: str
    git_blob: str
    sha256: str
    provided_in_input: bool


def attest_source(context: WorkspaceContext, logical_name, *, content=None):
    require(
        isinstance(logical_name, str) and logical_name and "\0" not in logical_name,
        "Invalid compiler source unit",
    )
    logical = Path(logical_name)
    physical = (
        logical if logical.is_absolute()
        else context.project_root / logical
    ).resolve(strict=True)
    require(
        physical.is_file()
        and physical.is_relative_to(context.repository_root),
        "Compiler source outside checkout",
    )
    owner, revision = attest_owner(context.repository_root, physical)
    relative = physical.relative_to(owner).as_posix()
    mode, blob = index_entry(owner, relative)
    require(mode in {"100644", "100755"}, "Compiler source not a tracked regular file")
    raw = physical.read_bytes()
    digest = git(owner, "hash-object", "--no-filters", "--", str(physical))
    require(blob == digest, "Compiler source differs from pinned Git blob")
    if content is not None:
        require(isinstance(content, str), "Unsupported compiler source content")
        require(raw == content.encode("utf-8"), "Compiler content differs from Git source")
    return AttestedSource(
        logical_name=logical_name,
        repository_path=physical.relative_to(context.repository_root).as_posix(),
        owner_path=(
            "." if owner == context.repository_root
            else owner.relative_to(context.repository_root).as_posix()
        ),
        owner_commit=revision,
        git_blob=blob,
        sha256=hashlib.sha256(raw).hexdigest(),
        provided_in_input=content is not None,
    )


def attest_build_sources(context, build_info):
    """Attest all compiler source units, including import-only names.

    Missing logical names must not be added to the original input.sources,
    since that can alter compiler AST IDs.
    """
    require(isinstance(build_info, dict), "Invalid compiler build info")
    document = build_info.get("input")
    output = build_info.get("output")
    require(
        isinstance(document, dict) and isinstance(output, dict)
        and isinstance(document.get("sources"), dict)
        and isinstance(output.get("sources"), dict),
        "Missing compiler source mappings",
    )
    provided = document["sources"]
    compiled = output["sources"]
    require(bool(provided) and bool(compiled), "Empty compiler source mapping")
    results = []
    for logical in sorted(set(provided) | set(compiled)):
        if logical in provided:
            entry = provided[logical]
            require(
                isinstance(entry, dict) and isinstance(entry.get("content"), str),
                "Unsupported source input (content required)",
            )
            content = entry["content"]
        else:
            content = None
        results.append(attest_source(context, logical, content=content))
    return tuple(results)


def materialize_imports(context, attested, destination):
    """Copy missing imports into a temporary snapshot workspace.

    Caller must constrain solc filesystem access to the snapshot's parent
    and preserve the original Standard JSON input unchanged.
    """
    destination = Path(destination).resolve()
    require(
        not destination.is_relative_to(context.repository_root),
        "Snapshot cannot write into consumer checkout",
    )
    require(destination.is_dir(), "Missing snapshot directory")
    copied = []
    for entry in attested:
        if entry.provided_in_input:
            continue
        logical = Path(entry.logical_name)
        require(not logical.is_absolute(), "Absolute missing import")
        source = (context.repository_root / entry.repository_path).resolve()
        path = (destination / logical).resolve()
        require(
            path.is_relative_to(destination.parent),
            "Snapshot escapes allowed root",
        )
        require(not path.exists(), "Duplicate snapshot source")
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        require(
            hashlib.sha256(raw).hexdigest() == entry.sha256,
            "Source changed after attestation",
        )
        path.write_bytes(raw)
        copied.append(entry.logical_name)
    return tuple(copied)
