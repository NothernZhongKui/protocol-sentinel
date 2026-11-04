#!/usr/bin/env python3
"""Adversarial unit tests for the standalone v0.6 workspace context."""

import shutil
import subprocess
import tempfile
from pathlib import Path

from workspace_context import WorkspaceError, resolve_workspace


def git(path, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(f"git {' '.join(args)}: {result.stderr}")
    return result.stdout.strip()


def init(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Workspace Fixture")
    git(path, "config", "user.email", "workspace@example.invalid")


def commit(path, message):
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)


def reject(label, call, reason):
    try:
        call()
    except WorkspaceError as exc:
        assert reason in str(exc), (label, str(exc))
        print(f"PASS | Reject {label}: {exc}")
    else:
        raise AssertionError(f"Accepted invalid context: {label}")


def main():
    with tempfile.TemporaryDirectory(prefix="sentinel-context-") as tmp:
        root = Path(tmp)
        tool_repo = root / "tool-src"
        repo = root / "consumer"
        init(tool_repo)
        (tool_repo / "scripts").mkdir()
        (tool_repo / "scripts/run_portable_direct.py").write_text(
            "# pinned tool entrypoint\n", encoding="utf-8"
        )
        commit(tool_repo, "tool fixture")
        init(repo)
        for name in ("capu", "other"):
            workspace = repo / "projects" / name
            workspace.mkdir(parents=True)
            (workspace / "foundry.toml").write_text(
                "[profile.default]\n", encoding="utf-8"
            )
        commit(repo, "two independent workspaces")

        git(
            repo,
            "-c", "protocol.file.allow=always",
            "submodule", "add", "-q",
            str(tool_repo), "projects/capu/lib/protocol-sentinel",
        )
        commit(repo, "pin tool submodule")
        project = repo / "projects/capu"
        tool = project / "lib/protocol-sentinel"
        context = resolve_workspace(
            project, tool, expected_workspace="projects/capu"
        )
        assert context.repository_root == repo.resolve()
        assert context.workspace == "projects/capu"
        assert context.tool_path == "projects/capu/lib/protocol-sentinel"
        assert context.repository_commit == git(repo, "rev-parse", "HEAD")
        assert context.tool_commit == git(tool, "rev-parse", "HEAD")
        print("PASS | Nested workspace, exact gitlink, commit and tool identity")

        reject(
            "wrong trusted workspace",
            lambda: resolve_workspace(project, tool, expected_workspace="projects/other"),
            "Trusted workspace mismatch",
        )
        reject(
            "untrusted parent traversal",
            lambda: resolve_workspace(project, tool, expected_workspace="../capu"),
            "Unsafe workspace identity",
        )
        reject(
            "absolute trusted workspace",
            lambda: resolve_workspace(project, tool, expected_workspace=str(project)),
            "Unsafe workspace identity",
        )
        reject(
            "duplicate producer in sibling workspace",
            lambda: resolve_workspace(
                repo / "projects/other", tool, expected_workspace="projects/capu"
            ),
            "Trusted workspace mismatch",
        )
        reject(
            "outside checked-out tool",
            lambda: resolve_workspace(project, tool_repo),
            "Tool outside checkout",
        )
        other = root / "external-project"
        other.mkdir()
        (other / "foundry.toml").write_text("[profile.default]\n")
        reject(
            "outside workspace",
            lambda: resolve_workspace(other, tool),
            "Git command failed",
        )

        # Deliberately add an untracked file in the consumer checkout.
        (repo / "projects/capu" / "untracked.sol").write_text(
            "pragma solidity ^0.8.24;\n"
        )
        reject(
            "dirty consumer",
            lambda: resolve_workspace(project, tool),
            "Dirty consumer checkout",
        )
        (repo / "projects/capu" / "untracked.sol").unlink()

        (tool / "scripts/run_portable_direct.py").write_text("# modified\n")
        reject(
            "dirty tool",
            lambda: resolve_workspace(project, tool),
            "Dirty consumer checkout",
        )
        git(tool, "checkout", "--", "scripts/run_portable_direct.py")

        # A new commit changes the tool HEAD, but not the parent's gitlink.
        (tool / "extra.txt").write_text("new\n")
        commit(tool, "untracked revision")
        reject(
            "incorrect pinned revision",
            lambda: resolve_workspace(project, tool, require_clean=False),
            "Submodule revision mismatch",
        )
        git(tool, "checkout", "-q", "--detach", context.tool_commit)

        # Relocation must preserve relative identities.
        relocated_parent = root / "renamed-root"
        relocated_parent.mkdir()
        relocated = relocated_parent / "consumer"
        shutil.move(str(repo), str(relocated))
        updated = resolve_workspace(
            relocated / "projects/capu",
            relocated / "projects/capu/lib/protocol-sentinel",
            expected_workspace="projects/capu",
        )
        assert updated.repository_commit == context.repository_commit
        assert updated.tool_commit == context.tool_commit
        assert updated.workspace == context.workspace
        print("PASS | Relocated checkout retains stable workspace identity")

    print("=== WORKSPACE CONTEXT CONTROLS PASSED ===")


if __name__ == "__main__":
    main()
