// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ComparativeAuthorityProbe} from "../src/ComparativeAuthorityProbe.sol";

import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {RoleVaultV1, RoleVaultV2Risky, RoleVaultV2Fixed, RoleVaultCandidate} from "./fixtures/RoleVaultVersions.sol";

contract ComparativeAuthorityIntegrationTest is ComparativeAuthorityProbe {
    address internal governor;
    address internal operator;

    ERC1967Proxy internal proxy;
    RoleVaultV1 internal vault;

    address internal originalImplementation;

    function setUp() public {
        governor = makeAddr("comparison-governor");
        operator = makeAddr("comparison-operator");

        RoleVaultV1 initial = new RoleVaultV1();

        originalImplementation = address(initial);

        bytes memory initData = abi.encodeCall(RoleVaultV1.initialize, (governor, operator));

        proxy = new ERC1967Proxy(address(initial), initData);

        vault = RoleVaultV1(address(proxy));
    }

    function _word(address implementation) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(implementation)));
    }

    function _spec(address candidate) internal view returns (UpgradeCheck memory) {
        return UpgradeCheck({
            actor: operator,
            target: address(proxy),
            candidate: candidate,
            expectedRevert: abi.encodeWithSignature(
                "AccessControlUnauthorizedAccount(address,bytes32)", operator, vault.UPGRADER_ROLE()
            ),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });
    }

    function _install(address implementation) internal {
        vm.prank(governor, governor);

        vault.upgradeToAndCall(implementation, bytes(""));

        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), _word(implementation));
    }

    function _capture(UpgradeCheck memory spec, address activeImplementation)
        internal
        returns (DirectStage memory stage)
    {
        bytes32 originalSlot = vm.load(address(proxy), ERC1967_IMPL_SLOT);

        assertEq(originalSlot, _word(activeImplementation));

        DetailedUpgradeCheckResult memory detailed = _checkIsolatedUpgradeDetailed(spec);

        assertTrue(detailed.observation.targetValidAtObservation);

        assertTrue(detailed.observation.candidateValidAtObservation);

        assertEq(detailed.observation.implementationBefore, originalSlot);

        // The isolated probe must restore proxy storage.
        assertEq(vm.load(address(proxy), ERC1967_IMPL_SLOT), originalSlot);

        // The probe must not change the authorization roles.
        assertTrue(vault.hasRole(vault.UPGRADER_ROLE(), governor));

        assertFalse(vault.hasRole(vault.UPGRADER_ROLE(), operator));

        assertTrue(vault.hasRole(vault.OPERATOR_ROLE(), operator));

        stage = DirectStage({expectedActiveImplementation: activeImplementation, observation: detailed.observation});
    }

    function _assertComparison(
        UpgradeCheck memory spec,
        DirectStage memory beforeStage,
        DirectStage memory afterStage,
        PolicyStatus expectedBefore,
        PolicyStatus expectedAfter,
        ComparisonVerdict expectedVerdict
    ) internal pure {
        DirectComparisonResult memory result = _compareDirectUpgrade(
            keccak256("real-uups-upgrade-scenario"), spec, beforeStage, afterStage
        );

        assertEq(uint256(result.beforeEvaluation.status), uint256(expectedBefore));

        assertEq(uint256(result.afterEvaluation.status), uint256(expectedAfter));

        assertEq(uint256(result.verdict), uint256(expectedVerdict));

        assertEq(uint256(result.reason), uint256(ComparisonReason.NONE));
    }

    function test_RealUUPS_PassFailPass() public {
        RoleVaultV2Risky risky = new RoleVaultV2Risky();
        RoleVaultV2Fixed fixedVersion = new RoleVaultV2Fixed();
        RoleVaultCandidate candidate = new RoleVaultCandidate();

        UpgradeCheck memory spec = _spec(address(candidate));

        // Stage 1: original implementation denies operator.
        DirectStage memory baseline = _capture(spec, originalImplementation);

        assertFalse(baseline.observation.success);

        // Authorized governor installs the risky version.
        _install(address(risky));

        assertEq(vault.version(), 2);

        // Stage 2: operator can now upgrade the proxy.
        DirectStage memory riskyStage = _capture(spec, address(risky));

        assertTrue(riskyStage.observation.success);

        assertEq(riskyStage.observation.implementationAfter, _word(address(candidate)));

        _assertComparison(
            spec, baseline, riskyStage, PolicyStatus.PASS, PolicyStatus.FAIL, ComparisonVerdict.CHANGED_TO_VIOLATION
        );

        // Governor installs the corrected version.
        _install(address(fixedVersion));

        // Stage 3: operator loses the unintended authority.
        DirectStage memory fixedStage = _capture(spec, address(fixedVersion));

        assertFalse(fixedStage.observation.success);

        _assertComparison(
            spec, riskyStage, fixedStage, PolicyStatus.FAIL, PolicyStatus.PASS, ComparisonVerdict.CHANGED_TO_SATISFIED
        );

        // The original and fixed restrictions are preserved.
        _assertComparison(
            spec, baseline, fixedStage, PolicyStatus.PASS, PolicyStatus.PASS, ComparisonVerdict.STILL_SATISFIED
        );

        // Positive control: governor still retains upgrade authority.
        _install(address(candidate));

        assertEq(vault.version(), 3);
    }

    function test_RealUUPS_FailToFail() public {
        RoleVaultV2Risky firstRisky = new RoleVaultV2Risky();

        RoleVaultV2Risky secondRisky = new RoleVaultV2Risky();

        RoleVaultCandidate candidate = new RoleVaultCandidate();

        UpgradeCheck memory spec = _spec(address(candidate));

        _install(address(firstRisky));

        DirectStage memory first = _capture(spec, address(firstRisky));

        _install(address(secondRisky));

        DirectStage memory second = _capture(spec, address(secondRisky));

        _assertComparison(spec, first, second, PolicyStatus.FAIL, PolicyStatus.FAIL, ComparisonVerdict.STILL_VIOLATED);
    }

    function test_RealUUPS_SecondPolicy() public {
        RoleVaultV2Risky risky = new RoleVaultV2Risky();
        RoleVaultCandidate candidate = new RoleVaultCandidate();

        UpgradeCheck memory spec = _spec(address(candidate));

        spec.policy = UpgradePolicy.NO_SUCCESSFUL_UPGRADE_CALL;

        DirectStage memory baseline = _capture(spec, originalImplementation);

        _install(address(risky));

        DirectStage memory updated = _capture(spec, address(risky));

        _assertComparison(
            spec, baseline, updated, PolicyStatus.PASS, PolicyStatus.FAIL, ComparisonVerdict.CHANGED_TO_VIOLATION
        );
    }
}
