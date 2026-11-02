// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {OwnableUpgradeable} from "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";

import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

// TEST ONLY: deliberately over-permissive authorization.
// Not an implementation from the real Adapter8004 project.
contract TestOnlyOverPermissiveAdapter is OwnableUpgradeable, UUPSUpgradeable {
    address internal immutable extraUpgrader;

    constructor(address extraUpgrader_) {
        extraUpgrader = extraUpgrader_;
        _disableInitializers();
    }

    function _authorizeUpgrade(address) internal view override {
        if (_msgSender() != extraUpgrader) {
            _checkOwner();
        }
    }
}

// TEST ONLY: restored owner-only authorization.
// Also not an implementation from the real Adapter8004 project.
contract TestOnlyOwnerRestrictedAdapter is OwnableUpgradeable, UUPSUpgradeable {
    constructor() {
        _disableInitializers();
    }

    function _authorizeUpgrade(address) internal override onlyOwner {}
}
