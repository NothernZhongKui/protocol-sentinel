// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {RoleAuthorityRegressionTest} from "./RoleAuthorityRegression.t.sol";
import {RoleVaultV2Risky, RoleVaultV2Fixed, RoleVaultCandidate} from "./fixtures/RoleVaultVersions.sol";

contract AuthorityIsolationFuzzTest is RoleAuthorityRegressionTest {
    function _checkSingleProbe(address candidate, bytes32 originalSlot, bool risky, UpgradePolicy policy) internal {
        UpgradeCheck memory spec = UpgradeCheck({
            actor: operator,
            target: address(roleProxy),
            candidate: candidate,
            expectedRevert: abi.encodeWithSignature(
                "AccessControlUnauthorizedAccount(address,bytes32)", operator, vault.UPGRADER_ROLE()
            ),
            policy: policy
        });

        DetailedUpgradeCheckResult memory result = _checkIsolatedUpgradeDetailed(spec);

        assertTrue(result.observation.targetValidAtObservation);
        assertTrue(result.observation.candidateValidAtObservation);

        assertEq(result.observation.implementationBefore, originalSlot);

        if (risky) {
            assertTrue(result.observation.success);
            assertEq(uint256(result.status), uint256(PolicyStatus.FAIL));
            assertEq(result.observation.implementationAfter, _word(candidate));
        } else {
            assertFalse(result.observation.success);
            assertEq(uint256(result.status), uint256(PolicyStatus.PASS));
            assertEq(result.observation.implementationAfter, originalSlot);
        }

        assertEq(uint256(result.reason), uint256(PolicyReason.NONE));

        assertEq(vm.load(address(roleProxy), ERC1967_IMPL_SLOT), originalSlot);

        assertEq(vault.version(), 2);
        assertTrue(vault.hasRole(vault.UPGRADER_ROLE(), governor));
        assertFalse(vault.hasRole(vault.UPGRADER_ROLE(), operator));
        assertTrue(vault.hasRole(vault.OPERATOR_ROLE(), operator));
    }

    function testFuzz_RepeatedProbesPreserveAuthority(
        bool risky,
        bool strictPolicy,
        uint8 repeatSeed,
        uint256 candidateSelection
    ) public {
        address active;

        if (risky) {
            RoleVaultV2Risky implementation = new RoleVaultV2Risky();
            active = address(implementation);
        } else {
            RoleVaultV2Fixed implementation = new RoleVaultV2Fixed();
            active = address(implementation);
        }

        RoleVaultCandidate candidateA = new RoleVaultCandidate();
        RoleVaultCandidate candidateB = new RoleVaultCandidate();

        _install(active);

        bytes32 originalSlot = vm.load(address(roleProxy), ERC1967_IMPL_SLOT);

        assertEq(originalSlot, _word(active));
        assertEq(vault.version(), 2);

        UpgradePolicy policy =
            strictPolicy ? UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL : UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT;

        uint256 repeats = uint256(repeatSeed % 8) + 1;

        for (uint256 i; i < repeats; ++i) {
            address candidate = ((candidateSelection >> i) & 1) == 0 ? address(candidateA) : address(candidateB);

            _checkSingleProbe(candidate, originalSlot, risky, policy);
        }

        _install(address(candidateA));

        assertEq(vm.load(address(roleProxy), ERC1967_IMPL_SLOT), _word(address(candidateA)));

        assertEq(vault.version(), 3);
        assertTrue(vault.hasRole(vault.UPGRADER_ROLE(), governor));
        assertFalse(vault.hasRole(vault.UPGRADER_ROLE(), operator));
    }

    function testFuzz_InvalidCandidateNeverPasses(uint256 seed, bool risky) public {
        RoleVaultV2Risky riskyImplementation = new RoleVaultV2Risky();
        RoleVaultV2Fixed fixedImplementation = new RoleVaultV2Fixed();

        _install(risky ? address(riskyImplementation) : address(fixedImplementation));

        address candidate = address(uint160(uint256(keccak256(abi.encode(seed, "invalid-candidate")))));

        vm.assume(candidate.code.length == 0);

        bytes32 originalSlot = vm.load(address(roleProxy), ERC1967_IMPL_SLOT);

        UpgradeCheck memory spec = UpgradeCheck({
            actor: operator,
            target: address(roleProxy),
            candidate: candidate,
            expectedRevert: abi.encodeWithSignature(
                "AccessControlUnauthorizedAccount(address,bytes32)", operator, vault.UPGRADER_ROLE()
            ),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });

        DetailedUpgradeCheckResult memory result = _checkIsolatedUpgradeDetailed(spec);

        assertEq(uint256(result.status), uint256(PolicyStatus.UNKNOWN));

        assertEq(uint256(result.reason), uint256(PolicyReason.INVALID_CANDIDATE));

        assertEq(vm.load(address(roleProxy), ERC1967_IMPL_SLOT), originalSlot);
    }
}
