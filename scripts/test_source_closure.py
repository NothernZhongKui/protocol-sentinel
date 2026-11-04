#!/usr/bin/env python3
"""Positive and adversarial source closure tests using local Git fixtures."""

import json
import tempfile
from pathlib import Path

from source_closure import (
    SourceClosureError, attest_build_sources, attest_source, materialize_imports
)
from test_workspace_context import init, commit, git
from workspace_context import resolve_workspace


def reject(label, run, reason):
    try:
        run()
    except (SourceClosureError, ValueError) as exc:
        assert reason in str(exc), (label, str(exc))
        print(f"PASS | Reject {label}")
    else:
        raise AssertionError(f"Accepted {label}")


def main():
    with tempfile.TemporaryDirectory(prefix="sentinel-sources-") as tmp:
        base = Path(tmp)
        repo = base / "consumer"
        tool_source = base / "sentinel-src"
        init(tool_source)
        (tool_source / "scripts").mkdir()
        (tool_source / "scripts" / "run_portable_direct.py").write_text("# tool\n")
        (tool_source / "src").mkdir()
        (tool_source / "src" / "Capture.sol").write_text("contract Capture {}\n")
        commit(tool_source, "initial tool")

        init(repo)
        project = repo / "projects/capu"
        project.mkdir(parents=True)
        (project / "foundry.toml").write_text("[profile.default]\n")
        (project / "src").mkdir()
        (project / "src" / "Capu.sol").write_text("contract Capu {}\n")
        adjacent = repo / "projects/cap-staking/src"
        adjacent.mkdir(parents=True)
        (adjacent / "Shared.sol").write_text("contract Shared {}\n")
        commit(repo, "consumer sources")

        git(
            repo, "-c", "protocol.file.allow=always",
            "submodule", "add", "-q", str(tool_source),
            "projects/capu/lib/protocol-sentinel",
        )
        commit(repo, "pin tool")
        tool = project / "lib/protocol-sentinel"
        context = resolve_workspace(
            project, tool, expected_workspace="projects/capu",
        )

        info = {
            "input": {
                "sources": {
                    "src/Capu.sol": {
                        "content": "contract Capu {}\n",
                    },
                    "lib/protocol-sentinel/src/Capture.sol": {
                        "content": "contract Capture {}\n",
                    },
                },
            },
            "output": {
                "sources": {
                    "src/Capu.sol": {"id": 0},
                    "lib/protocol-sentinel/src/Capture.sol": {"id": 1},
                    "../cap-staking/src/Shared.sol": {"id": 2},
                },
            },
        }
        result = attest_build_sources(context, info)
        assert len(result) == 3
        assert sum(x.provided_in_input for x in result) == 2
        assert {x.owner_path for x in result} == {
            ".", "projects/capu/lib/protocol-sentinel"
        }
        print("PASS | Root, submodule, and adjacent-workspace source closure")

        sandbox = base / "snapshot"
        workspace = sandbox / "projects/capu"
        workspace.mkdir(parents=True)
        copied = materialize_imports(context, result, workspace)
        assert copied == ("../cap-staking/src/Shared.sol",)
        assert (
            sandbox / "projects/cap-staking/src/Shared.sol"
        ).read_text() == "contract Shared {}\n"
        print("PASS | Isolated snapshot with original source names")

        bad_info = json.loads(json.dumps(info))
        bad_info["input"]["sources"]["src/Capu.sol"]["content"] = "modified"
        reject(
            "input source forgery",
            lambda: attest_build_sources(context, bad_info),
            "Compiler content differs",
        )

        file = project / "src/Capu.sol"
        file.write_text("contract Forged {}\n")
        reject(
            "modified tracked source",
            lambda: attest_build_sources(context, info),
            "pinned Git blob",
        )
        git(repo, "checkout", "--", "projects/capu/src/Capu.sol")

        (project / "src/Untracked.sol").write_text("contract Untracked {}\n")
        reject(
            "untracked source",
            lambda: attest_source(context, "src/Untracked.sol"),
            "Source not uniquely tracked",
        )
        (project / "src/Untracked.sol").unlink()

        (project / "src/Shortcut.sol").symlink_to(
            project / "src/Capu.sol"
        )
        # Resolving symlink aliases to tracked bytes alone is insufficient
        # to attest the logical path; source unit identity needs separate
        # anti-alias validation before v0.6 Evidence publication.
        reject(
            "source outside checkout",
            lambda: attest_source(context, "/etc/hosts"),
            "Source outside checkout",
        )
        (project / "src/Shortcut.sol").unlink()

        missing_info = json.loads(json.dumps(info))
        missing_info["output"]["sources"]["../../../../escape.sol"] = {"id": 3}
        reject(
            "path escape",
            lambda: attest_build_sources(context, missing_info),
            "Source outside checkout",
        )

    print("=== GIT SOURCE CLOSURE CONTROLS PASSED ===")


if __name__ == "__main__":
    main()
