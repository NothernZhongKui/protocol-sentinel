// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {DirectComparisonCapture} from "../src/DirectComparisonCapture.sol";

import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

import {RoleVaultV1, RoleVaultV2Risky, RoleVaultCandidate} from "./fixtures/RoleVaultVersions.sol";

contract UnsupportedActorFixture {}

contract DirectComparisonCaptureLibraryTest is DirectComparisonCapture {
    address internal governor;
    address internal operator;

    ERC1967Proxy internal proxy;
    RoleVaultV1 internal vault;

    function setUp() public {
        governor = makeAddr("portable-governor");
        operator = makeAddr("portable-operator");

        RoleVaultV1 initial = new RoleVaultV1();

        bytes memory initialization = abi.encodeCall(RoleVaultV1.initialize, (governor, operator));

        proxy = new ERC1967Proxy(address(initial), initialization);

        vault = RoleVaultV1(address(proxy));
    }

    function _spec(address actor) internal returns (UpgradeCheck memory) {
        RoleVaultCandidate candidate = new RoleVaultCandidate();

        return UpgradeCheck({
            actor: actor,
            target: address(proxy),
            candidate: address(candidate),
            expectedRevert: abi.encodeWithSignature(
                "AccessControlUnauthorizedAccount(address,bytes32)", actor, vault.UPGRADER_ROLE()
            ),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });
    }

    function test_CapturePortableDirectComparison() public {
        RoleVaultV2Risky risky = new RoleVaultV2Risky();

        UpgradeCheck memory spec = _spec(operator);

        bytes32 scenarioId = keccak256("portable-direct-capture-smoke");

        DirectStage memory beforeStage = _observeDirectStage(spec);

        vm.prank(governor, governor);

        vault.upgradeToAndCall(address(risky), bytes(""));

        DirectStage memory afterStage = _observeDirectStage(spec);

        DirectComparisonResult memory result = _compareDirectUpgrade(scenarioId, spec, beforeStage, afterStage);

        assertEq(uint256(result.beforeEvaluation.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.afterEvaluation.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(result.verdict), uint256(ComparisonVerdict.CHANGED_TO_VIOLATION));

        _exportDirectComparison(scenarioId, spec, beforeStage, afterStage, result);
    }

    // External frame required by Foundry expectRevert.
    function observeForActorAdmission(UpgradeCheck memory spec) external {
        _observeDirectStage(spec);
    }

    function test_RejectContractActorBeforeExecution() public {
        UnsupportedActorFixture actor = new UnsupportedActorFixture();

        UpgradeCheck memory spec = _spec(address(actor));

        vm.expectRevert(abi.encodeWithSelector(UnsupportedDirectActor.selector, address(actor)));

        this.observeForActorAdmission(spec);
    }

    function test_RejectZeroActor() public {
        UpgradeCheck memory spec = _spec(address(0));

        vm.expectRevert(abi.encodeWithSelector(UnsupportedDirectActor.selector, address(0)));

        this.observeForActorAdmission(spec);
    }
}
