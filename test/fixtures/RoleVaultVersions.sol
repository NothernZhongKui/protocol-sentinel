// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";

import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

contract RoleVaultV1 is AccessControlUpgradeable, UUPSUpgradeable {
    bytes32 public constant UPGRADER_ROLE = keccak256("UPGRADER_ROLE");
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    constructor() {
        _disableInitializers();
    }

    function initialize(address governor, address operator) external initializer {
        require(governor != address(0), "Invalid governor");
        require(operator != address(0), "Invalid operator");
        require(governor != operator, "Roles must differ");

        __AccessControl_init();
        __UUPSUpgradeable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, governor);
        _grantRole(UPGRADER_ROLE, governor);
        _grantRole(OPERATOR_ROLE, operator);
    }

    function version() external pure virtual returns (uint256) {
        return 1;
    }

    function _authorizeUpgrade(address) internal view virtual override onlyRole(UPGRADER_ROLE) {}
}

contract RoleVaultV2Risky is RoleVaultV1 {
    function version() external pure override returns (uint256) {
        return 2;
    }

    // Intentional regression:
    // OPERATOR_ROLE now bypasses UPGRADER_ROLE.
    function _authorizeUpgrade(address) internal view override {
        if (!hasRole(OPERATOR_ROLE, _msgSender())) {
            _checkRole(UPGRADER_ROLE, _msgSender());
        }
    }
}

contract RoleVaultV2Fixed is RoleVaultV1 {
    function version() external pure override returns (uint256) {
        return 2;
    }
}

contract RoleVaultCandidate is RoleVaultV1 {
    function version() external pure override returns (uint256) {
        return 3;
    }
}
