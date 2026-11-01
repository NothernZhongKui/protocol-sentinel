// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {OwnableUpgradeable} from "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

contract VaultV1 is OwnableUpgradeable, UUPSUpgradeable {
    address public operator;

    constructor() {
        _disableInitializers();
    }

    function initialize(address timelock, address operator_) external initializer {
        require(timelock != address(0), "Invalid timelock");
        require(operator_ != address(0), "Invalid operator");
        require(operator_ != timelock, "Roles must differ");

        __Ownable_init(timelock);
        __UUPSUpgradeable_init();

        operator = operator_;
    }

    function version() external pure virtual returns (uint256) {
        return 1;
    }

    function _authorizeUpgrade(address) internal virtual override onlyOwner {}
}
