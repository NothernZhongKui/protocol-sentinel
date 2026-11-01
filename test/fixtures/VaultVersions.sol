// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {VaultV1} from "../../src/VaultV1.sol";

contract VaultV2Risky is VaultV1 {
    function version() external pure override returns (uint256) {
        return 2;
    }

    function _authorizeUpgrade(address) internal override {
        if (msg.sender != owner() && msg.sender != operator) {
            revert OwnableUnauthorizedAccount(msg.sender);
        }
    }
}

contract UpgradeProbe is VaultV1 {
    function version() external pure override returns (uint256) {
        return 3;
    }
}

contract VaultV2Fixed is VaultV1 {
    function version() external pure override returns (uint256) {
        return 2;
    }
}
