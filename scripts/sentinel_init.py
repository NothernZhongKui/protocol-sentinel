#!/usr/bin/env python3
"""Conservative Direct UUPS producer scaffold for an existing Foundry workspace.

No role, proxy, expected revert, or authorized migration is invented. The
generated producer compiles but fails its test with SentinelFixtureIncomplete
until a developer supplies the actual invariant.
"""

import argparse
import sys
from pathlib import Path

from workspace_context import resolve_workspace

SCENARIO = "0x" + "0" * 63 + "1"

SOURCE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Fill in your own fixture below. Do not treat this scaffold as a security test.
// Keep the existing Foundry dependency remappings for forge-std.
import {DirectComparisonCapture} from "../lib/protocol-sentinel/src/DirectComparisonCapture.sol";

contract SentinelAuthorityProducerTest is DirectComparisonCapture {
    error SentinelFixtureIncomplete();

    // TODO: deploy your V1 proxy and a valid, separate UUPS probe candidate.
    // TODO: choose the actual actor who must NOT acquire upgrade authority.
    // TODO: set the exact expected authorization revert, using your ABI.
    // TODO: choose NO_IMPLEMENTATION_REPLACEMENT or NO_SUCCESSFUL_UPGRADE_CALL.
    function _createFixture() internal virtual returns (UpgradeCheck memory) {
        revert SentinelFixtureIncomplete();
    }

    // TODO: install your V2 implementation through the real authorized route.
    // A direct upgrade used for the fixture is NOT the unauthorized actor probe.
    function _performAuthorizedUpgrade() internal virtual {
        revert SentinelFixtureIncomplete();
    }

    function test_ProduceSentinelAuthorityComparison() public {
        UpgradeCheck memory spec = _createFixture();
        DirectStage memory beforeStage = _observeDirectStage(spec);

        _performAuthorizedUpgrade();

        DirectStage memory afterStage = _observeDirectStage(spec);
        bytes32 scenarioId = SCENARIO_ID;

        DirectComparisonResult memory comparison =
            _compareDirectUpgrade(scenarioId, spec, beforeStage, afterStage);
        _exportDirectComparison(scenarioId, spec, beforeStage, afterStage, comparison);
    }

    // TODO: replace this placeholder identity consistently in sentinel.toml.
    bytes32 private constant SCENARIO_ID = __SCENARIO__;
}
""".replace("__SCENARIO__", SCENARIO)

CONFIG = """[sentinel]
config_version = "1"
route = "DIRECT_EOA_UUPS"

[producer]
id = "sentinel_direct_uups"
contract = "SentinelAuthorityProducerTest"
test = "test_ProduceSentinelAuthorityComparison"
source = "test/SentinelAuthorityProducer.t.sol"
fixture_id = "sentinel-direct-uups-placeholder"
scenario_id = "__SCENARIO__"
""".replace("__SCENARIO__", SCENARIO)


def initialize(project, tool, *, dry_run=False):
    project = Path(project).resolve()
    tool = Path(tool).resolve()
    if not (project / "foundry.toml").is_file():
        raise ValueError("Expected an existing Foundry workspace with foundry.toml")

    # Ensure the generator is the pinned tool actually installed in this consumer.
    context = resolve_workspace(project, tool, require_clean=False)
    if context.tool_root != Path(__file__).resolve().parents[1]:
        raise ValueError("Run init from the installed, Git-pinned Sentinel submodule")

    paths = [
        (project / "test/SentinelAuthorityProducer.t.sol", SOURCE),
        (project / "sentinel.toml", CONFIG),
    ]
    for path, _ in paths:
        if path.exists() or path.is_symlink():
            raise ValueError(f"Refusing to overwrite existing file: {path}")
        if not path.parent.exists() or not path.parent.is_dir():
            raise ValueError(f"Expected existing Foundry test directory: {path.parent}")
        if path.parent.is_symlink():
            raise ValueError(f"Refusing symlinked output parent: {path.parent}")
        if not path.resolve().is_relative_to(context.project_root):
            raise ValueError("Scaffold output escapes workspace")

    if dry_run:
        return [path for path, _ in paths]

    created = []
    try:
        for path, value in paths:
            with path.open("x", encoding="utf-8") as stream:
                created.append(path)
                stream.write(value)
    except OSError:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return created


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Existing Foundry workspace")
    parser.add_argument("--route", choices=("direct-uups",), required=True)
    parser.add_argument("--tool-root", help="Pinned Sentinel gitlink; defaults to <project>/lib/protocol-sentinel")
    parser.add_argument("--dry-run", action="store_true", help="Show proposed files; write nothing")
    args = parser.parse_args(argv)
    project = Path(args.project).resolve()
    tool = Path(args.tool_root).resolve() if args.tool_root else project / "lib/protocol-sentinel"
    try:
        paths = initialize(project, tool, dry_run=args.dry_run)
    except (OSError, ValueError) as exc:
        print(f"INIT FAILED: {exc}", file=sys.stderr)
        return 1
    print("Protocol Sentinel — Direct UUPS scaffold")
    for path in paths:
        print(f"{'WOULD CREATE' if args.dry_run else 'CREATED'}  {path.relative_to(project)}")
    if not args.dry_run:
        print("INCOMPLETE: the generated producing test reverts SentinelFixtureIncomplete().")
        print("Define actor, proxy, probe candidate, expected revert, and authorized V1 → V2 transition.")
        print("Update fixture_id and scenario_id consistently before treating this as a real scenario.")
        print("Merge the Evidence fs_permissions and ignore rule into your existing workspace config.")
        print("Commit intended inputs before running the authoritative workspace runner.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
