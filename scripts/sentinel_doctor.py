#!/usr/bin/env python3
"""Read-only, offline preflight for a Git-pinned Sentinel Direct UUPS consumer.

This command is advisory. Only the actual workspace runner may attest a fresh
compiler source closure, publish Evidence, or make a trusted CI decision.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from producer_config import read_config
from source_closure import attest_source
from workspace_context import resolve_workspace

OUTPUT = Path("artifacts/sentinel/runs")
VERSION = re.compile(r"\bVersion:\s*([0-9]+\.[0-9]+\.[0-9]+)(?:\+commit\.[0-9a-fA-F]+)?")


def _git(cwd, *args):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False,
    )
    return result.returncode, result.stdout.strip()


def _check_path(value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value.endswith(".toml"):
        raise ValueError("Config must be a workspace-relative .toml path without '..'")
    return path


def _permissions(path):
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    profiles = data.get("profile", {})
    default = profiles.get("default", {}) if isinstance(profiles, dict) else {}
    if not isinstance(default, dict):
        raise ValueError("Invalid [profile.default] configuration")
    entries = default.get("fs_permissions", [])
    if not isinstance(entries, list):
        raise ValueError("Invalid fs_permissions array")
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("access") != "read-write":
            continue
        value = entry.get("path")
        if not isinstance(value, str):
            continue
        # The runner writes under the workspace, not an arbitrary sibling.
        norm = value.removeprefix("./").rstrip("/")
        if norm in {"artifacts/sentinel", "artifacts/sentinel/runs", "."}:
            return True
    return False


def inspect(project, tool, config_name, solc):
    """Return (status, message) pairs without modifying the checkout."""
    rows = []

    def emit(status, message):
        rows.append((status, message))

    project = Path(project).resolve()
    tool = Path(tool).resolve()
    context = None

    config_file = project / "foundry.toml"
    if not config_file.is_file():
        emit("FAIL", f"Foundry workspace missing: {config_file}")
    else:
        emit("PASS", "Foundry workspace detected")
        try:
            if _permissions(config_file):
                emit("PASS", "Evidence write permission declared")
            else:
                emit("FAIL", "Add read-write fs_permissions for artifacts/sentinel/runs to foundry.toml")
        except (ValueError, OSError, tomllib.TOMLDecodeError) as exc:
            emit("FAIL", f"Invalid foundry.toml: {exc}")

    returncode, repository = _git(project, "rev-parse", "--show-toplevel") if project.is_dir() else (1, "")
    if returncode:
        emit("FAIL", "Foundry workspace must be inside a Git checkout")
    else:
        root = Path(repository).resolve()
        status, dirty = _git(root, "status", "--porcelain", "--untracked-files=all")
        if status:
            emit("FAIL", "Unable to inspect consumer Git working tree")
        elif dirty:
            emit("WARN", "Consumer checkout has changes; commit intended inputs before verified execution")
        else:
            emit("PASS", "Consumer Git checkout clean")

        try:
            context = resolve_workspace(project, tool, require_clean=False)
            emit("PASS", f"Pinned Sentinel gitlink verified ({context.tool_commit[:12]})")
        except (OSError, ValueError) as exc:
            emit("FAIL", f"Sentinel gitlink verification: {exc}")

        ignored, _ = _git(project, "check-ignore", "-q", "--", str(OUTPUT / "probe"))
        if ignored == 0:
            emit("PASS", "Evidence output is Git-ignored")
        else:
            emit("FAIL", "Add artifacts/sentinel/runs/ to workspace .gitignore")

    try:
        relative = _check_path(config_name)
        config_file = (project / relative).resolve()
        if not config_file.is_relative_to(project) or not config_file.is_file():
            raise ValueError("Config missing or outside workspace")
        producer = read_config(config_file)
        emit("PASS", f"Producer configuration valid ({producer['id']})")
        source = (project / producer["source"]).resolve()
        if not source.is_relative_to(project) or not source.is_file():
            emit("FAIL", f"Producer source missing or outside workspace: {producer['source']}")
        else:
            emit("PASS", f"Producer source present: {producer['source']}")
        if context is not None:
            try:
                attest_source(context, relative.as_posix())
                owner = attest_source(context, producer["source"])
                if owner.owner_path != ".":
                    emit("FAIL", "Producer source must be owned by consumer Git checkout")
                else:
                    emit("PASS", "Producer and configuration match tracked Git blobs")
            except (ValueError, OSError) as exc:
                emit("FAIL", f"Tracked producer/config: {exc}")
        else:
            emit("DEFERRED", "Producer Git source ownership until Sentinel gitlink is valid")
    except (ValueError, OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        emit("FAIL", f"Producer configuration: {exc}")

    if shutil.which("forge"):
        emit("PASS", "Foundry forge available")
    else:
        emit("FAIL", "Install Foundry and add forge to PATH")

    if solc is None:
        emit("WARN", "Supply --solc /absolute/path/to/solc for compiler identity preflight")
    else:
        compiler = Path(solc)
        if not compiler.is_absolute() or not compiler.is_file() or not os.access(compiler, os.X_OK):
            emit("FAIL", "--solc must be an absolute path to an executable compiler")
        else:
            try:
                proc = subprocess.run(
                    [str(compiler), "--version"], capture_output=True, text=True,
                    check=False, timeout=10,
                )
                found = VERSION.search(proc.stdout + "\n" + proc.stderr)
                if proc.returncode or found is None:
                    emit("FAIL", "Compiler did not return a recognized solc --version")
                else:
                    emit("PASS", f"Solc executable reports {found.group(1)}")
            except (OSError, subprocess.TimeoutExpired) as exc:
                emit("FAIL", f"Unable to inspect solc: {exc}")

    emit("DEFERRED", "Effective Foundry remappings, compiler imports and source closure until fresh build")
    emit("DEFERRED", "Trusted policy and merge enforcement until protected CI run")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Existing Foundry workspace")
    parser.add_argument("--tool-root", help="Sentinel gitlink; defaults to <project>/lib/protocol-sentinel")
    parser.add_argument("--config", default="sentinel.toml", help="Tracked producer configuration")
    parser.add_argument("--solc", help="Absolute compiler executable path")
    args = parser.parse_args(argv)
    project = Path(args.project).resolve()
    tool = Path(args.tool_root).resolve() if args.tool_root else project / "lib/protocol-sentinel"

    print("Protocol Sentinel — Doctor (advisory / read-only)", flush=True)
    try:
        rows = inspect(project, tool, args.config, args.solc)
    except (OSError, ValueError) as exc:
        print(f"FAIL  Preflight could not finish: {exc}")
        return 1
    for status, message in rows:
        print(f"{status:<8}{message}")
    failures = sum(status == "FAIL" for status, _ in rows)
    print(f"\nLOCAL PREFLIGHT: {'NOT READY' if failures else 'NO KNOWN BLOCKERS'}")
    print("NOT A CI APPROVAL — the workspace runner repeats all authoritative checks.")
    return int(failures > 0)


if __name__ == "__main__":
    sys.exit(main())
