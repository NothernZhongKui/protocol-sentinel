#!/usr/bin/env python3
"""v0.6 build manifest capture/verification and mutation controls."""

import json
import tempfile
from pathlib import Path

from test_workspace_context import init, commit, git
from workspace_context import resolve_workspace
from replay_workspace_build import replay_unit
from workspace_provenance import (
    WorkspaceProvenanceError, capture_v2, verify_v2,
)


def reject(label, function, reason):
    try:
        function()
    except (WorkspaceProvenanceError, ValueError) as exc:
        assert reason in str(exc), (label, str(exc))
        print(f"PASS | Rejected {label}")
    else:
        raise AssertionError(f"Accepted {label}")


def main():
    with tempfile.TemporaryDirectory(prefix="sentinel-v2-") as temp:
        base = Path(temp)
        root = base / "consumer"
        tool_src = base / "tool"
        init(tool_src)
        (tool_src / "src").mkdir()
        (tool_src / "src/Capture.sol").write_text("contract Capture {}\n")
        (tool_src / "scripts").mkdir()
        (tool_src / "scripts/run_portable_direct.py").write_text("# tool\n")
        commit(tool_src, "tool")

        init(root)
        (root / "foundry.toml").write_text("[profile.default]\nsolc = '0.8.26'\n")
        project = root / "projects/capu"
        (project / "test").mkdir(parents=True)
        (project / "foundry.toml").write_text(
            "[profile.default]\nextends = '../../foundry.toml'\n"
        )
        (project / "test/Oracle.t.sol").write_text("contract Oracle {}\n")
        commit(root, "consumer")

        git(
            root, "-c", "protocol.file.allow=always",
            "submodule", "add", "-q", str(tool_src),
            "projects/capu/lib/protocol-sentinel",
        )
        commit(root, "pinned dependencies")
        tool = project / "lib/protocol-sentinel"
        context = resolve_workspace(
            project, tool, expected_workspace="projects/capu"
        )

        fresh = base / "fresh"
        fresh.mkdir()
        original = {
            "solcVersion": "0.8.26",
            "input": {
                "language": "Solidity",
                "sources": {
                    "test/Oracle.t.sol": {"content": "contract Oracle {}\n"},
                    "lib/protocol-sentinel/src/Capture.sol": {
                        "content": "contract Capture {}\n"
                    },
                },
                "settings": {"optimizer": {"enabled": True, "runs": 200}},
            },
            "output": {
                "sources": {
                    "test/Oracle.t.sol": {"id": 0},
                    "lib/protocol-sentinel/src/Capture.sol": {"id": 1},
                },
                "contracts": {
                    "test/Oracle.t.sol": {
                        "Oracle": {
                            "abi": [],
                            "evm": {
                                "bytecode": {"object": "6000"},
                                "deployedBytecode": {"object": "6000"},
                            },
                        },
                    },
                },
            },
        }
        (fresh / "unit.json").write_text(json.dumps(original))
        bundle = base / "bundle"
        digest = capture_v2(context, fresh, bundle, "test/Oracle.t.sol")
        assert digest == verify_v2(context, bundle, "test/Oracle.t.sol")
        manifest = json.loads((bundle / "build-provenance.json").read_text())
        assert manifest["format"] == "protocol-sentinel-build-provenance-v2"
        assert manifest["workspace"] == "projects/capu"
        assert any(
            entry["path"] == "foundry.toml"
            for entry in manifest["integrationInputs"]
        )
        assert any(
            entry["path"] == "projects/capu/foundry.toml"
            for entry in manifest["integrationInputs"]
        )
        print("PASS | V2 capture, exact manifest, inherited config pinning")

        # Deterministic mock compiler: tests the replay wiring and strict
        # comparison, NOT actual Solidity compilation.
        fake = base / "fake-solc"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "if '--version' in sys.argv:\n"
            "    print('Version: 0.8.26+commit.8a97fa7a.Linux.g++')\n"
            "    sys.exit(0)\n"
            "sys.stdin.buffer.read()\n"
            "print(" + repr(json.dumps(original["output"])) + ")\n"
        )
        fake.chmod(0o755)
        report = replay_unit(context, original, fake)
        assert report["contracts"] == 1
        assert report["source_units"] == 2
        assert report["snapshot_imports"] == 0
        print("PASS | Standalone replay plumbing with deterministic mock compiler")

        unknown = dict(original, solcVersion="0.8.25")
        fake_unknown = base / "fake-solc-unknown"
        fake_unknown.write_text(fake.read_text().replace(
            "0.8.26+commit.8a97fa7a", "0.8.25+commit.b61c2a91"
        ))
        fake_unknown.chmod(0o755)
        reject(
            "unknown short compiler version without exact identity",
            lambda: replay_unit(context, unknown, fake_unknown),
            "Missing exact compiler build identity",
        )
        # Same semver, incorrect recorded build commit: no recompile can bless it.
        mismatched = dict(original, solcVersion="0.8.26+commit.00000000")
        reject(
            "mismatched recorded compiler commit",
            lambda: replay_unit(context, mismatched, fake),
            "Compiler commit mismatch",
        )
        short_long = dict(original, solcLongVersion="0.8.26")
        assert replay_unit(context, short_long, fake)["contracts"] == 1
        print("PASS | Foundry short solcLongVersion with pinned exact commit")
        reject(
            "short long-version with unexpected installed commit",
            lambda: replay_unit(context, short_long, fake_other),
            "Compiler commit mismatch",
        )

        decorated_long = dict(
            original,
            solcLongVersion="solc, the solidity compiler\nVersion: 0.8.26+commit.8a97fa7a.Linux.g++",
        )
        assert replay_unit(context, decorated_long, fake)["contracts"] == 1
        print("PASS | Foundry-style full compiler descriptor with exact commit")

        misleading_long = dict(original, solcLongVersion="0.8.26+commit.00000000")
        reject(
            "mismatched recorded long compiler identity",
            lambda: replay_unit(context, misleading_long, fake),
            "Compiler commit mismatch",
        )
        fake_other = base / "fake-solc-other"
        fake_other.write_text(fake.read_text().replace(
            "0.8.26+commit.8a97fa7a", "0.8.26+commit.00000000"
        ))
        fake_other.chmod(0o755)
        reject(
            "short compiler version with wrong installed commit",
            lambda: replay_unit(context, original, fake_other),
            "Compiler commit mismatch",
        )

        original_fake = fake.read_text()
        fake.write_text(original_fake.replace("6000", "6001"))
        reject(
            "changed compiler output bytecode",
            lambda: replay_unit(context, original, fake),
            "CONTRACTS MISMATCH",
        )
        fake.write_text(original_fake)

        unexpected = bundle / "unexpected.txt"
        unexpected.write_text("unverified artifact\n")
        reject(
            "unexpected build bundle entry",
            lambda: verify_v2(context, bundle, "test/Oracle.t.sol"),
            "Unexpected build bundle contents",
        )
        unexpected.unlink()

        path = bundle / "build-info/unit.json"
        original_bytes = path.read_bytes()
        path.write_bytes(original_bytes + b"\n")
        reject(
            "changed build-info",
            lambda: verify_v2(context, bundle, "test/Oracle.t.sol"),
            "V2 manifest does not match",
        )
        path.write_bytes(original_bytes)
        assert verify_v2(context, bundle, "test/Oracle.t.sol") == digest

        manifest_path = bundle / "build-provenance.json"
        original_manifest = manifest_path.read_bytes()
        modified = json.loads(original_manifest)
        modified["workspace"] = "projects/other"
        manifest_path.write_text(json.dumps(modified))
        reject(
            "wrong workspace identity",
            lambda: verify_v2(context, bundle, "test/Oracle.t.sol"),
            "V2 manifest does not match",
        )
        manifest_path.write_bytes(original_manifest)

        modified = json.loads(original_manifest)
        modified["unsupported"] = "ignored"
        manifest_path.write_text(json.dumps(modified))
        reject(
            "unsupported manifest field",
            lambda: verify_v2(context, bundle, "test/Oracle.t.sol"),
            "Unexpected v2 manifest fields",
        )
        manifest_path.write_bytes(original_manifest)

        modified = json.loads(original_manifest)
        modified["format"] = "protocol-sentinel-build-provenance-v1"
        manifest_path.write_text(json.dumps(modified))
        reject(
            "v2 downgrade to v1",
            lambda: verify_v2(context, bundle, "test/Oracle.t.sol"),
            "Unsupported manifest version",
        )
        manifest_path.write_bytes(original_manifest)

        (project / "test/Oracle.t.sol").write_text("contract Forged {}\n")
        reject(
            "changed tracked producer source",
            lambda: verify_v2(context, bundle, "test/Oracle.t.sol"),
            "pinned Git blob",
        )
        git(root, "checkout", "--", "projects/capu/test/Oracle.t.sol")

        # Positive monorepo case with no repository-root foundry.toml.
        (root / "foundry.toml").unlink()
        (project / "foundry.toml").write_text(
            "[profile.default]\nsolc = '0.8.26'\n"
        )
        commit(root, "standalone nested Foundry workspace")
        nested_context = resolve_workspace(
            project, tool, expected_workspace="projects/capu"
        )
        standalone = base / "standalone-bundle"
        capture_v2(nested_context, fresh, standalone, "test/Oracle.t.sol")
        standalone_manifest = json.loads(
            (standalone / "build-provenance.json").read_text()
        )
        paths = {entry["path"] for entry in standalone_manifest["integrationInputs"]}
        assert "foundry.toml" not in paths
        assert "projects/capu/foundry.toml" in paths
        verify_v2(nested_context, standalone, "test/Oracle.t.sol")
        print("PASS | Nested standalone workspace without root foundry.toml")

    print("=== WORKSPACE PROVENANCE V2 CONTROLS PASSED ===")


if __name__ == "__main__":
    main()
