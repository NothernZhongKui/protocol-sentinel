// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract NonUUPSImplementation {
    function version() external pure returns (uint256) {
        return 99;
    }
}
