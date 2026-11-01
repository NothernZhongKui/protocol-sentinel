// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";

abstract contract AuthorityProbe is Test {
    enum PolicyStatus {
        PASS,
        FAIL,
        UNKNOWN,
        ERROR
    }

    enum UpgradePolicy {
        NO_IMPLEMENTATION_REPLACEMENT,
        NO_SUCCESSFUL_UPGRADE_CALL
    }

    bytes32 internal constant ERC1967_IMPL_SLOT = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    struct Observation {
        address actor;
        address txOrigin;
        address target;
        bool success;
        bytes returnData;
        bytes32 observedSlot;
        bytes32 implementationBefore;
        bytes32 implementationAfter;
        bytes callData;
        bool candidateValidAtObservation;
    }

    // Observation layer: record what actually happened.
    function _observeCall(address actor, address target, bytes memory callData, bytes32 implementationSlot)
        internal
        returns (Observation memory result)
    {
        result.actor = actor;
        result.txOrigin = actor;
        result.target = target;
        result.callData = callData;

        // Capture candidate preconditions BEFORE execution.
        // This PoC supports the canonical upgradeToAndCall(address,bytes)
        // encoding with empty initialization data.
        if (callData.length == 100) {
            address candidate;

            assembly {
                candidate := mload(add(callData, 36))
            }

            bytes memory canonicalCallData =
                abi.encodeWithSignature("upgradeToAndCall(address,bytes)", candidate, bytes(""));

            if (keccak256(callData) == keccak256(canonicalCallData)) {
                result.candidateValidAtObservation = _isValidUUPSImplementation(candidate);
            }
        }

        result.observedSlot = implementationSlot;
        result.implementationBefore = vm.load(target, implementationSlot);

        // Direct EOA execution: sender and origin are the same.
        // Contract-mediated calls require a separate execution adapter.
        vm.prank(actor, actor);
        (result.success, result.returnData) = target.call(callData);

        result.implementationAfter = vm.load(target, implementationSlot);
    }

    // Execute a probe and restore the original EVM state.
    // Observation remains available in memory.
    function _observeIsolatedCall(address actor, address target, bytes memory callData, bytes32 implementationSlot)
        internal
        returns (Observation memory result)
    {
        uint256 snapshotId = vm.snapshotState();

        result = _observeCall(actor, target, callData, implementationSlot);

        bool restored = vm.revertToStateAndDelete(snapshotId);

        require(restored, "Sentinel: snapshot restore failed");
    }

    // Preconditions for our known UUPS fixture.
    function _isValidUUPSImplementation(address candidate) internal view returns (bool) {
        if (candidate.code.length == 0) {
            return false;
        }

        (bool success, bytes memory response) = candidate.staticcall(abi.encodeWithSignature("proxiableUUID()"));

        if (!success || response.length != 32) {
            return false;
        }

        return abi.decode(response, (bytes32)) == ERC1967_IMPL_SLOT;
    }

    // Policy layer: interpret an observation.
    function _evaluateUpgradePolicy(
        Observation memory obs,
        UpgradePolicy policy,
        bytes32 expectedImplementation,
        bytes memory expectedRevert,
        address expectedActor,
        address expectedTarget
    ) internal pure returns (PolicyStatus) {
        // ERC-1967 policies require the actual implementation slot.
        // An unrelated storage observation cannot justify PASS or FAIL.
        if (obs.observedSlot != ERC1967_IMPL_SLOT) {
            return PolicyStatus.UNKNOWN;
        }

        // Direct EOA observation requires matching sender and origin.
        // Contract-mediated execution is outside the current scope.
        if (
            obs.actor != expectedActor
                || obs.txOrigin != expectedActor
                || obs.target != expectedTarget
        ) {
            return PolicyStatus.UNKNOWN;
        }

        address candidate = address(uint160(uint256(expectedImplementation)));

        // This PoC covers upgradeToAndCall with empty data.
        bytes memory expectedCallData = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", candidate, bytes(""));

        if (keccak256(obs.callData) != keccak256(expectedCallData)) {
            return PolicyStatus.UNKNOWN;
        }

        // ERC-1967 implementation addresses occupy the lower 160 bits.
        // Preserve full storage words in Observation for diagnostics.
        address implementationBefore =
            address(uint160(uint256(obs.implementationBefore)));

        address implementationAfter =
            address(uint160(uint256(obs.implementationAfter)));

        bool unchanged = implementationBefore == implementationAfter;

        if (!obs.success) {
            // A rejected upgrade is meaningful only with a valid candidate.
            if (!obs.candidateValidAtObservation) {
                return PolicyStatus.UNKNOWN;
            }

            if (unchanged && keccak256(obs.returnData) == keccak256(expectedRevert)) {
                return PolicyStatus.PASS;
            }

            return PolicyStatus.UNKNOWN;
        }

        if (policy == UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL) {
            return PolicyStatus.FAIL;
        }

        // Any successful implementation replacement violates this policy,
        // even when the installed address differs from the requested candidate.
        if (!unchanged) {
            return PolicyStatus.FAIL;
        }

        return PolicyStatus.UNKNOWN;
    }

    // Compatibility with existing regression tests.
    function _classifyUpgrade(
        Observation memory obs,
        bytes32 expectedImplementation,
        bytes memory expectedRevert,
        address expectedActor,
        address expectedTarget
    ) internal pure returns (PolicyStatus) {
        return _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            expectedImplementation,
            expectedRevert,
            expectedActor,
            expectedTarget
        );
    }

    // Convenience API for a direct EOA, ERC-1967 UUPS upgrade probe.
    // Only canonical upgradeToAndCall with empty initialization data.
    struct UpgradeCheck {
        address actor;
        address target;
        address candidate;
        bytes expectedRevert;
        UpgradePolicy policy;
    }

    struct UpgradeCheckResult {
        Observation observation;
        PolicyStatus status;
    }

    function _checkIsolatedUpgrade(
        UpgradeCheck memory spec
    ) internal returns (UpgradeCheckResult memory result) {
        bytes memory payload = abi.encodeWithSignature(
            "upgradeToAndCall(address,bytes)",
            spec.candidate,
            bytes("")
        );

        result.observation = _observeIsolatedCall(
            spec.actor,
            spec.target,
            payload,
            ERC1967_IMPL_SLOT
        );

        result.status = _evaluateUpgradePolicy(
            result.observation,
            spec.policy,
            bytes32(uint256(uint160(spec.candidate))),
            spec.expectedRevert,
            spec.actor,
            spec.target
        );
    }

}
