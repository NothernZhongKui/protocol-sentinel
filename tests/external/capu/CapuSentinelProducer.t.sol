// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {DirectComparisonCapture} from
    "../lib/protocol-sentinel/src/DirectComparisonCapture.sol";

import {IAccessControl} from
    "@openzeppelin/contracts/access/IAccessControl.sol";

import {Fixture} from "./helpers/Fixture.sol";

import {
    CapuSafePilotV2,
    CapuFaultyPilotV2,
    CapuProbeCandidate
} from "./AuthorityRegressionOracle.t.sol";

contract CapuSentinelProducerTest is
    Fixture,
    DirectComparisonCapture
{
    address internal actor;
    CapuProbeCandidate internal probe;

    function setUp() public {
        _deployStack();

        actor = makeAddr("sentinel-outsider");
        probe = new CapuProbeCandidate();
    }

    function _record(bool faulty)
        internal
        returns (DirectComparisonResult memory result)
    {
        UpgradeCheck memory spec = UpgradeCheck({
            actor: actor,
            target: address(capu),
            candidate: address(probe),
            expectedRevert: abi.encodeWithSelector(
                IAccessControl
                    .AccessControlUnauthorizedAccount
                    .selector,
                actor,
                bytes32(0)
            ),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });

        // Observation 1: baseline.
        DirectStage memory beforeStage =
            _observeDirectStage(spec);

        // Authorized implementation transition.
        if (faulty) {
            CapuFaultyPilotV2 updated =
                new CapuFaultyPilotV2();

            vm.prank(admin);
            capu.upgradeToAndCall(
                address(updated),
                abi.encodeCall(
                    CapuFaultyPilotV2.migratePilotRole,
                    (actor)
                )
            );
        } else {
            CapuSafePilotV2 updated =
                new CapuSafePilotV2();

            vm.prank(admin);
            capu.upgradeToAndCall(
                address(updated),
                ""
            );
        }

        // Observation 2: updated implementation.
        DirectStage memory afterStage =
            _observeDirectStage(spec);

        bytes32 scenarioId = faulty
            ? keccak256("capu-pilot-faulty-v1")
            : keccak256("capu-pilot-safe-v1");

        result = _compareDirectUpgrade(
            scenarioId,
            spec,
            beforeStage,
            afterStage
        );

        // Only writes when Sentinel export is enabled.
        _exportDirectComparison(
            scenarioId,
            spec,
            beforeStage,
            afterStage,
            result
        );
    }

    // CI-style producers: do not assert a safe verdict.
    function test_ProduceSafe() public {
        _record(false);
    }

    function test_ProduceFaulty() public {
        _record(true);
    }

    // Separate local assertions of Solidity classification.
    function test_AssertSafeClassification() public {
        DirectComparisonResult memory result =
            _record(false);

        assertEq(
            uint256(result.beforeEvaluation.status),
            uint256(PolicyStatus.PASS)
        );

        assertEq(
            uint256(result.afterEvaluation.status),
            uint256(PolicyStatus.PASS)
        );

        assertEq(
            uint256(result.verdict),
            uint256(ComparisonVerdict.STILL_SATISFIED)
        );
    }

    function test_AssertFaultyClassification() public {
        DirectComparisonResult memory result =
            _record(true);

        assertEq(
            uint256(result.beforeEvaluation.status),
            uint256(PolicyStatus.PASS)
        );

        assertEq(
            uint256(result.afterEvaluation.status),
            uint256(PolicyStatus.FAIL)
        );

        assertEq(
            uint256(result.verdict),
            uint256(ComparisonVerdict.CHANGED_TO_VIOLATION)
        );
    }
}
