#!/usr/bin/env python3
"""Verified Git/Foundry workspace identity for a portable consumer.

This is a v0.6 foundation, not an Evidence writer or CI authorization.
A trusted caller must supply expected_workspace from protected policy,
never solely from the candidate branch.
"""

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SHA = re.compile(r"[0-9a-f]{40}\Z")


class WorkspaceError(ValueError):
    pass


@dataclass(frozen=True)
class WorkspaceContext:
    repository_root: Path
    project_root: Path
    tool_root: Path
    workspace: str
    tool_path: str
    repository_commit: str
    tool_commit: str


def _require(condition, message):
    if not condition:
        raise WorkspaceError(message)


def _git(directory, *args):
    process = subprocess.run(
        ["git", *args],
        cwd=directory,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        process.returncode == 0,
        f"Git command failed: {' '.join(args)}",
    )
    return process.stdout.strip()


def _relative_path(value):
    _require(isinstance(value, str) and value != "", "Invalid workspace identity")
    path = PurePosixPath(value)
    _require(
        value == "."
        or (
            not path.is_absolute()
            and ".." not in path.parts
            and path.as_posix() == value
            and value != "."
        ),
        "Unsafe workspace identity",
    )
    return value


def _verify_gitlink(parent, child):
    _require(child != parent and child.is_relative_to(parent), "Invalid submodule parent")
    relative = child.relative_to(parent).as_posix()
    lines = _git(parent, "ls-files", "--stage", "--", relative).splitlines()
    _require(len(lines) == 1 and "\t" in lines[0], "Missing submodule gitlink")
    metadata, actual_path = lines[0].split("\t", 1)
    fields = metadata.split()
    _require(
        len(fields) == 3
        and fields[0] == "160000"
        and fields[2] == "0"
        and actual_path == relative,
        "Invalid submodule gitlink",
    )
    actual_revision = _git(child, "rev-parse", "HEAD")
    _require(
        SHA.fullmatch(actual_revision) is not None
        and fields[1] == actual_revision,
        "Submodule revision mismatch",
    )
    _require(
        not _git(child, "status", "--porcelain", "--untracked-files=all"),
        "Dirty submodule",
    )
    return actual_revision


def resolve_workspace(project, tool, *, expected_workspace=None, require_clean=True):
    """Verify a nested workspace and installed tool against a Git checkout.

    The tool must be a pinned Git submodule, possibly nested within other
    pinned submodules. This function does not authenticate a CI workflow,
    validate compiler sources, or permit Evidence publication.
    """
    project = Path(project).resolve()
    tool = Path(tool).resolve()
    _require(
        project.is_dir() and (project / "foundry.toml").is_file(),
        "Missing Foundry workspace",
    )
    repository = Path(_git(project, "rev-parse", "--show-toplevel")).resolve()
    _require(
        repository.is_dir() and project.is_relative_to(repository),
        "Workspace outside Git checkout",
    )
    _require(
        tool.is_dir()
        and tool.is_relative_to(repository)
        and tool != repository
        and (tool / "scripts/run_portable_direct.py").is_file(),
        "Tool outside checkout or missing entrypoint",
    )

    workspace = project.relative_to(repository).as_posix()
    _relative_path(workspace)
    if expected_workspace is not None:
        expected = _relative_path(expected_workspace)
        _require(workspace == expected, "Trusted workspace mismatch")

    repository_commit = _git(repository, "rev-parse", "HEAD")
    _require(SHA.fullmatch(repository_commit) is not None, "Invalid consumer commit")
    if require_clean:
        _require(
            not _git(repository, "status", "--porcelain", "--untracked-files=all"),
            "Dirty consumer checkout",
        )

    current = tool
    tool_commit = _git(tool, "rev-parse", "HEAD")
    _require(SHA.fullmatch(tool_commit) is not None, "Invalid tool commit")
    visited = set()

    while current != repository:
        _require(current not in visited, "Cyclic submodule chain")
        visited.add(current)
        parent_text = _git(current, "rev-parse", "--show-superproject-working-tree")
        _require(bool(parent_text), "Tool is not a registered Git submodule")
        parent = Path(parent_text).resolve()
        _require(
            parent == repository or parent.is_relative_to(repository),
            "Submodule parent outside checkout",
        )
        _verify_gitlink(parent, current)
        current = parent

    return WorkspaceContext(
        repository_root=repository,
        project_root=project,
        tool_root=tool,
        workspace=workspace,
        tool_path=tool.relative_to(repository).as_posix(),
        repository_commit=repository_commit,
        tool_commit=tool_commit,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--tool-root", required=True, type=Path)
    parser.add_argument("--expected-workspace")
    args = parser.parse_args()
    context = resolve_workspace(
        args.project, args.tool_root, expected_workspace=args.expected_workspace
    )
    print("REPOSITORY_ROOT:", context.repository_root)
    print("WORKSPACE:", context.workspace)
    print("TOOL_PATH:", context.tool_path)
    print("REPOSITORY_COMMIT:", context.repository_commit)
    print("TOOL_COMMIT:", context.tool_commit)
    print("WORKSPACE_CONTEXT: VERIFIED")
    print("EVIDENCE: NOT_EVALUATED")


if __name__ == "__main__":
    try:
        main()
    except WorkspaceError as exc:
        raise SystemExit(f"WORKSPACE_CONTEXT_FAILED: {exc}") from exc
