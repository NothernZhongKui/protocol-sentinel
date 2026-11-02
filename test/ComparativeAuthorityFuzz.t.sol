// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ComparativeAuthorityProbe} from "../src/ComparativeAuthorityProbe.sol";

contract ComparativeAuthorityFuzzTest is ComparativeAuthorityProbe {
    address internal constant ACTOR = address(0xBEEF);
    address internal constant TARGET = address(0xCAFE);
    address internal constant CANDIDATE = address(0xA11CE);

    address internal constant OLD_IMPL = address(0x1111);
    address internal constant NEW_IMPL = address(0x2222);

    function _word(address addr) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(addr)));
    }

    function _spec() internal pure returns (UpgradeCheck memory) {
        return UpgradeCheck({
            actor: ACTOR,
            target: TARGET,
            candidate: CANDIDATE,
            expectedRevert: abi.encodeWithSignature("Forbidden(address)", ACTOR),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });
    }

    function _stage(address implementation, bool succeeds) internal pure returns (DirectStage memory) {
        UpgradeCheck memory spec = _spec();

        Observation memory obs = Observation({
            actor: ACTOR,
            txOrigin: ACTOR,
            target: TARGET,
            success: succeeds,
            returnData: succeeds ? bytes("") : spec.expectedRevert,
            observedSlot: ERC1967_IMPL_SLOT,
            implementationBefore: _word(implementation),
            implementationAfter: succeeds ? _word(CANDIDATE) : _word(implementation),
            callData: abi.encodeWithSignature("upgradeToAndCall(address,bytes)", CANDIDATE, bytes("")),
            candidateValidAtObservation: true,
            targetValidAtObservation: true
        });

        return DirectStage({expectedActiveImplementation: implementation, observation: obs});
    }

    function _compare(DirectStage memory beforeStage, DirectStage memory afterStage)
        internal
        pure
        returns (DirectComparisonResult memory)
    {
        return _compareDirectUpgrade(keccak256("fuzz-authority-scenario"), _spec(), beforeStage, afterStage);
    }

    function testFuzz_TransitionTable(bool beforeSucceeds, bool afterSucceeds) public pure {
        DirectComparisonResult memory result =
            _compare(_stage(OLD_IMPL, beforeSucceeds), _stage(NEW_IMPL, afterSucceeds));

        PolicyStatus expectedBefore = beforeSucceeds ? PolicyStatus.FAIL : PolicyStatus.PASS;

        PolicyStatus expectedAfter = afterSucceeds ? PolicyStatus.FAIL : PolicyStatus.PASS;

        ComparisonVerdict expectedVerdict;

        if (!beforeSucceeds && !afterSucceeds) {
            expectedVerdict = ComparisonVerdict.STILL_SATISFIED;
        } else if (!beforeSucceeds && afterSucceeds) {
            expectedVerdict = ComparisonVerdict.CHANGED_TO_VIOLATION;
        } else if (beforeSucceeds && !afterSucceeds) {
            expectedVerdict = ComparisonVerdict.CHANGED_TO_SATISFIED;
        } else {
            expectedVerdict = ComparisonVerdict.STILL_VIOLATED;
        }

        assertEq(uint256(result.beforeEvaluation.status), uint256(expectedBefore));

        assertEq(uint256(result.afterEvaluation.status), uint256(expectedAfter));

        assertEq(uint256(result.verdict), uint256(expectedVerdict));

        assertEq(uint256(result.reason), uint256(ComparisonReason.NONE));
    }

    function testFuzz_UpperBitsCannotChangeVerdict(
        uint96 beforeHigh,
        uint96 afterHigh,
        bool beforeSucceeds,
        bool afterSucceeds
    ) public pure {
        DirectStage memory beforeStage = _stage(OLD_IMPL, beforeSucceeds);

        DirectStage memory afterStage = _stage(NEW_IMPL, afterSucceeds);

        DirectComparisonResult memory baseline = _compare(beforeStage, afterStage);

        bytes32 beforeMask = bytes32(uint256(beforeHigh) << 160);

        bytes32 afterMask = bytes32(uint256(afterHigh) << 160);

        beforeStage.observation.implementationBefore |= beforeMask;
        beforeStage.observation.implementationAfter |= beforeMask;

        afterStage.observation.implementationBefore |= afterMask;
        afterStage.observation.implementationAfter |= afterMask;

        DirectComparisonResult memory mutated = _compare(beforeStage, afterStage);

        assertEq(uint256(mutated.verdict), uint256(baseline.verdict));

        assertEq(uint256(mutated.beforeEvaluation.status), uint256(baseline.beforeEvaluation.status));

        assertEq(uint256(mutated.afterEvaluation.status), uint256(baseline.afterEvaluation.status));
    }

    function testFuzz_UpperBitsCannotFakeNewVersion(uint96 firstHigh, uint96 secondHigh) public pure {
        DirectStage memory beforeStage = _stage(OLD_IMPL, false);

        DirectStage memory afterStage = _stage(OLD_IMPL, false);

        beforeStage.observation.implementationBefore |= bytes32(uint256(firstHigh) << 160);

        afterStage.observation.implementationBefore |= bytes32(uint256(secondHigh) << 160);

        DirectComparisonResult memory result = _compare(beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(ComparisonReason.SAME_IMPLEMENTATION_STAGE));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));
    }

    function testFuzz_ContextMismatchTakesPrecedence(uint160 mask) public pure {
        DirectStage memory beforeStage = _stage(OLD_IMPL, false);

        DirectStage memory afterStage = _stage(NEW_IMPL, true);

        // Always create an address different from ACTOR.
        beforeStage.observation.actor = address(uint160(ACTOR) ^ (mask | 1));

        DirectComparisonResult memory result = _compare(beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(ComparisonReason.SCENARIO_MISMATCH));

        // Both evaluations must have genuinely run.
        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.FAIL));
    }

    function testFuzz_StageMismatchPreservesEvaluations(uint160 mask) public pure {
        DirectStage memory beforeStage = _stage(OLD_IMPL, true);

        DirectStage memory afterStage = _stage(NEW_IMPL, false);

        beforeStage.expectedActiveImplementation = address(uint160(OLD_IMPL) ^ (mask | 1));

        DirectComparisonResult memory result = _compare(beforeStage, afterStage);

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INCOMPARABLE));

        assertEq(uint256(result.reason), uint256(ComparisonReason.STAGE_BINDING_MISMATCH));

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.PASS));
    }

    function testFuzz_UnexpectedRevertRemainsUnknown(bytes memory arbitraryData) public pure {
        DirectStage memory beforeStage = _stage(OLD_IMPL, false);

        DirectStage memory afterStage = _stage(NEW_IMPL, true);

        // Appending one byte guarantees a different revert payload.
        beforeStage.observation.returnData = bytes.concat(_spec().expectedRevert, arbitraryData, hex"01");

        DirectComparisonResult memory result = _compare(beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(result.beforeEvaluation.reason), uint256(PolicyReason.UNEXPECTED_REVERT));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.INDETERMINATE));
    }

    function testFuzz_ScenarioKeyBindsDeclaredFields(
        bytes32 scenarioId,
        uint160 actorMask,
        uint160 targetMask,
        uint160 candidateMask
    ) public pure {
        UpgradeCheck memory original = _spec();

        bytes32 key = _directScenarioKey(scenarioId, original);

        UpgradeCheck memory changed = _spec();

        changed.actor = address(uint160(ACTOR) ^ (actorMask | 1));

        assertTrue(key != _directScenarioKey(scenarioId, changed));

        changed = _spec();

        changed.target = address(uint160(TARGET) ^ (targetMask | 1));

        assertTrue(key != _directScenarioKey(scenarioId, changed));

        changed = _spec();

        changed.candidate = address(uint160(CANDIDATE) ^ (candidateMask | 1));

        assertTrue(key != _directScenarioKey(scenarioId, changed));

        changed = _spec();

        changed.policy = UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL;

        assertTrue(key != _directScenarioKey(scenarioId, changed));

        assertTrue(key != _directScenarioKey(scenarioId ^ bytes32(uint256(1)), original));

        assertEq(key, _directScenarioKey(scenarioId, original));
    }
}
