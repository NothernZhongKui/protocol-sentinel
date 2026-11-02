// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AuthorityProbe} from "../src/AuthorityProbe.sol";

interface IForkOwnable {
    function owner() external view returns (address);
}

contract Adapter8004MainnetForkTest is AuthorityProbe {
    uint256 internal constant FORK_BLOCK = 24995819;

    address internal constant PROXY = 0xde152AfB7db5373F34876E1499fbD893A82dD336;

    address internal constant ACTIVE_IMPL = 0xcdeFFf9EaFCfa28be798D1c1B1c8D731087d1CE4;

    address internal constant PREVIOUS_IMPL = 0xA54a604448A5Ab0AfFccdDa6228EC4F2ac12a586;

    address internal constant HISTORICAL_OWNER = 0xF8e03bd4436371E0e2F7C02E529b2172fe72b4EF;

    address internal constant OUTSIDER = address(0xBEEF);

    function _implementation() internal view returns (address) {
        return address(uint160(uint256(vm.load(PROXY, ERC1967_IMPL_SLOT))));
    }

    function _selectHistoricalFork() internal {
        vm.createSelectFork(vm.envString("ETH_RPC_URL"), FORK_BLOCK);

        assertEq(block.chainid, 1);
        assertEq(block.number, FORK_BLOCK);

        assertGt(PROXY.code.length, 0);
        assertGt(ACTIVE_IMPL.code.length, 0);
        assertGt(PREVIOUS_IMPL.code.length, 0);

        assertEq(_implementation(), ACTIVE_IMPL);

        assertEq(IForkOwnable(PROXY).owner(), HISTORICAL_OWNER);
    }

    function _spec(address actor) internal pure returns (UpgradeCheck memory) {
        return UpgradeCheck({
            actor: actor,
            target: PROXY,
            candidate: PREVIOUS_IMPL,
            expectedRevert: abi.encodeWithSignature("OwnableUnauthorizedAccount(address)", actor),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });
    }

    function testFork_NonOwnerCannotUpgrade() public {
        vm.skip(!vm.envOr("RUN_MAINNET_FORK", false));
        _selectHistoricalFork();

        bytes32 beforeSlot = vm.load(PROXY, ERC1967_IMPL_SLOT);

        DetailedUpgradeCheckResult memory result = _checkIsolatedUpgradeDetailed(_spec(OUTSIDER));

        assertTrue(result.observation.targetValidAtObservation);
        assertTrue(result.observation.candidateValidAtObservation);
        assertFalse(result.observation.success);

        assertEq(uint256(result.status), uint256(PolicyStatus.PASS));

        assertEq(uint256(result.reason), uint256(PolicyReason.NONE));

        assertEq(vm.load(PROXY, ERC1967_IMPL_SLOT), beforeSlot);
        assertEq(_implementation(), ACTIVE_IMPL);
    }

    function testFork_OwnerUpgradeDetectedAndRestored() public {
        vm.skip(!vm.envOr("RUN_MAINNET_FORK", false));
        _selectHistoricalFork();

        bytes32 beforeSlot = vm.load(PROXY, ERC1967_IMPL_SLOT);

        DetailedUpgradeCheckResult memory result = _checkIsolatedUpgradeDetailed(_spec(HISTORICAL_OWNER));

        assertTrue(result.observation.targetValidAtObservation);
        assertTrue(result.observation.candidateValidAtObservation);
        assertTrue(result.observation.success);

        assertEq(address(uint160(uint256(result.observation.implementationAfter))), PREVIOUS_IMPL);

        assertEq(uint256(result.status), uint256(PolicyStatus.FAIL));

        assertEq(uint256(result.reason), uint256(PolicyReason.NONE));

        assertEq(vm.load(PROXY, ERC1967_IMPL_SLOT), beforeSlot);
        assertEq(_implementation(), ACTIVE_IMPL);

        assertEq(IForkOwnable(PROXY).owner(), HISTORICAL_OWNER);
    }

    function testFork_HistoricalOwnerCanActuallyUpgrade() public {
        vm.skip(!vm.envOr("RUN_MAINNET_FORK", false));
        _selectHistoricalFork();

        bytes memory payload = abi.encodeWithSignature("upgradeToAndCall(address,bytes)", PREVIOUS_IMPL, bytes(""));

        vm.prank(HISTORICAL_OWNER, HISTORICAL_OWNER);

        (bool success,) = PROXY.call(payload);

        assertTrue(success, "Historical owner upgrade failed on local fork");

        assertEq(_implementation(), PREVIOUS_IMPL);

        assertEq(IForkOwnable(PROXY).owner(), HISTORICAL_OWNER);
    }
}
