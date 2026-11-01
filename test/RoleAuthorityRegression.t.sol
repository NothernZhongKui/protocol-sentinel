// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityProbe} from "./helpers/AuthorityProbe.sol";

import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {RoleVaultV1, RoleVaultV2Risky, RoleVaultV2Fixed, RoleVaultCandidate} from "./fixtures/RoleVaultVersions.sol";

contract RoleAuthorityRegressionTest is AuthorityProbe {
    address internal governor;
    address internal operator;

    ERC1967Proxy internal roleProxy;
    RoleVaultV1 internal vault;

    function setUp() public {
        governor = makeAddr("role-governor");
        operator = makeAddr("role-operator");

        RoleVaultV1 implementation = new RoleVaultV1();

        bytes memory initData = abi.encodeCall(RoleVaultV1.initialize, (governor, operator));

        roleProxy = new ERC1967Proxy(address(implementation), initData);

        vault = RoleVaultV1(address(roleProxy));
    }

    function _word(address account) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(account)));
    }

    function _install(address nextImplementation) internal {
        // Real authorized UUPS upgrade by the governor.
        vm.prank(governor, governor);
        vault.upgradeToAndCall(nextImplementation, bytes(""));
    }

    function _probe(address candidate) internal returns (Observation memory) {
        bytes memory callData = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", candidate, bytes(""));

        return _observeIsolatedCall(operator, address(roleProxy), callData, ERC1967_IMPL_SLOT);
    }

    function _verdict(Observation memory obs, address candidate) internal view returns (PolicyStatus) {
        bytes memory expectedRevert = abi.encodeWithSignature(
            "AccessControlUnauthorizedAccount(address,bytes32)", operator, vault.UPGRADER_ROLE()
        );

        return _evaluateUpgradePolicy(
            obs,
            UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT,
            _word(candidate),
            expectedRevert,
            operator,
            address(roleProxy)
        );
    }

    function test_RoleBaselineOperatorDenied() public {
        RoleVaultCandidate candidate = new RoleVaultCandidate();

        bytes32 initialImplementation = vm.load(address(roleProxy), ERC1967_IMPL_SLOT);

        Observation memory obs = _probe(address(candidate));

        assertFalse(obs.success);
        assertEq(obs.actor, operator);
        assertEq(obs.txOrigin, operator);

        assertEq(obs.implementationBefore, initialImplementation);
        assertEq(obs.implementationAfter, initialImplementation);

        assertEq(uint256(_verdict(obs, address(candidate))), uint256(PolicyStatus.PASS));
    }

    function test_RoleRiskyOperatorBypassDetected() public {
        RoleVaultV2Risky risky = new RoleVaultV2Risky();
        RoleVaultCandidate candidate = new RoleVaultCandidate();

        // The governor installs V2 via the authorized path.
        _install(address(risky));

        assertEq(vault.version(), 2);

        // Operator still does not possess the upgrade role.
        assertFalse(vault.hasRole(vault.UPGRADER_ROLE(), operator));
        assertTrue(vault.hasRole(vault.OPERATOR_ROLE(), operator));
        assertTrue(vault.hasRole(vault.UPGRADER_ROLE(), governor));

        Observation memory obs = _probe(address(candidate));

        assertTrue(obs.success);
        assertEq(obs.implementationBefore, _word(address(risky)));
        assertEq(obs.implementationAfter, _word(address(candidate)));

        assertEq(uint256(_verdict(obs, address(candidate))), uint256(PolicyStatus.FAIL));

        // The isolated probe must not alter the fixture.
        assertEq(vm.load(address(roleProxy), ERC1967_IMPL_SLOT), _word(address(risky)));

        assertEq(vault.version(), 2);
    }

    function test_RoleFixedOperatorDenied() public {
        RoleVaultV2Fixed fixedVersion = new RoleVaultV2Fixed();
        RoleVaultCandidate candidate = new RoleVaultCandidate();

        _install(address(fixedVersion));

        assertEq(vault.version(), 2);
        assertFalse(vault.hasRole(vault.UPGRADER_ROLE(), operator));

        Observation memory obs = _probe(address(candidate));

        assertFalse(obs.success);
        assertEq(obs.implementationBefore, _word(address(fixedVersion)));
        assertEq(obs.implementationAfter, _word(address(fixedVersion)));

        assertEq(uint256(_verdict(obs, address(candidate))), uint256(PolicyStatus.PASS));

        assertEq(vm.load(address(roleProxy), ERC1967_IMPL_SLOT), _word(address(fixedVersion)));
    }
}
