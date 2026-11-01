// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityProbe} from "../src/AuthorityProbe.sol";

contract PublicImportSmokeTest is AuthorityProbe {
    function test_PublicCoreCanBeImported() public {
        assertEq(uint256(PolicyStatus.PASS), 0);
        assertEq(uint256(PolicyStatus.FAIL), 1);
        assertEq(uint256(PolicyStatus.UNKNOWN), 2);

        assertEq(
            uint256(UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT),
            0
        );
    }
}
