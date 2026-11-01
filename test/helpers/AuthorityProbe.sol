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

    struct Observation {
        bool success;
        bytes returnData;
        bytes32 implementationBefore;
        bytes32 implementationAfter;
    }

    function _observeCall(address actor, address target, bytes memory callData, bytes32 implementationSlot)
        internal
        returns (Observation memory result)
    {
        result.implementationBefore = vm.load(target, implementationSlot);

        vm.prank(actor);
        (result.success, result.returnData) = target.call(callData);

        result.implementationAfter = vm.load(target, implementationSlot);
    }

    function _classifyUpgrade(Observation memory result, bytes32 expectedImplementation, bytes memory expectedRevert)
        internal
        view
        returns (PolicyStatus)
    {
        address candidate = address(uint160(uint256(expectedImplementation)));

        // Precondition 1: implementation must exist.
        if (candidate.code.length == 0) {
            return PolicyStatus.UNKNOWN;
        }

        // Precondition 2: confirm UUPS compatibility
        // for this ERC-1967 fixture.
        (bool valid, bytes memory response) = candidate.staticcall(abi.encodeWithSignature("proxiableUUID()"));

        bytes32 expectedSlot = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

        if (!valid || response.length != 32) {
            return PolicyStatus.UNKNOWN;
        }

        if (abi.decode(response, (bytes32)) != expectedSlot) {
            return PolicyStatus.UNKNOWN;
        }

        // Confirmed unauthorized implementation change.
        if (
            result.success && result.implementationAfter == expectedImplementation
                && result.implementationAfter != result.implementationBefore
        ) {
            return PolicyStatus.FAIL;
        }

        // Expected authorization rejection.
        if (
            !result.success && result.implementationAfter == result.implementationBefore
                && keccak256(result.returnData) == keccak256(expectedRevert)
        ) {
            return PolicyStatus.PASS;
        }

        return PolicyStatus.UNKNOWN;
    }
}
