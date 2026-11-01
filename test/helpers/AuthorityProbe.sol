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
        pure
        returns (PolicyStatus)
    {
        if (
            result.success && result.implementationAfter == expectedImplementation
                && result.implementationAfter != result.implementationBefore
        ) {
            return PolicyStatus.FAIL;
        }

        if (
            !result.success && result.implementationAfter == result.implementationBefore
                && keccak256(result.returnData) == keccak256(expectedRevert)
        ) {
            return PolicyStatus.PASS;
        }

        return PolicyStatus.UNKNOWN;
    }
}
