// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockAuthorityProbe} from "../src/TimelockAuthorityProbe.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

import {ProxyAdmin, ITransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

contract TimelockAuthorityTypesTest is TimelockAuthorityProbe {
    function _scenario() internal pure returns (TimelockScenario memory) {
        return TimelockScenario({
            timelock: address(0x1001),
            proposer: address(0x1002),
            executor: address(0x1003),
            proxyAdmin: address(0x2001),
            proxy: address(0x2002),
            candidate: address(0x2003),
            predecessor: bytes32(0),
            salt: keccak256("test-operation"),
            property: TimelockProperty.READY_UPGRADE_SUCCEEDS
        });
    }

    function test_CanonicalProxyAdminPayload() public pure {
        TimelockScenario memory spec = _scenario();

        bytes memory expected = abi.encodeCall(
            ProxyAdmin.upgradeAndCall, (ITransparentUpgradeableProxy(spec.proxy), spec.candidate, bytes(""))
        );

        assertEq(_timelockUpgradePayload(spec), expected);
    }

    function test_OperationIdMatchesPinnedOpenZeppelin() public {
        TimelockScenario memory spec = _scenario();

        address[] memory proposers = new address[](0);
        address[] memory executors = new address[](0);

        TimelockController controller = new TimelockController(48 hours, proposers, executors, address(0));

        bytes32 expected =
            controller.hashOperation(spec.proxyAdmin, 0, _timelockUpgradePayload(spec), spec.predecessor, spec.salt);

        assertEq(_timelockOperationId(spec), expected);
    }

    function test_OperationIdBindsTuple() public pure {
        TimelockScenario memory original = _scenario();

        bytes32 baseline = _timelockOperationId(original);

        TimelockScenario memory changed = _scenario();
        changed.proxyAdmin = address(0x9991);

        assertTrue(_timelockOperationId(changed) != baseline);

        changed = _scenario();
        changed.proxy = address(0x9992);

        assertTrue(_timelockOperationId(changed) != baseline);

        changed = _scenario();
        changed.candidate = address(0x9993);

        assertTrue(_timelockOperationId(changed) != baseline);

        changed = _scenario();
        changed.predecessor = keccak256("dependency");

        assertTrue(_timelockOperationId(changed) != baseline);

        changed = _scenario();
        changed.salt = keccak256("different-salt");

        assertTrue(_timelockOperationId(changed) != baseline);
    }

    function test_CanonicalOuterExecutePayload() public pure {
        TimelockScenario memory spec = _scenario();

        bytes memory expected = abi.encodeCall(
            TimelockController.execute,
            (spec.proxyAdmin, uint256(0), _timelockUpgradePayload(spec), spec.predecessor, spec.salt)
        );

        assertEq(_timelockExecutePayload(spec), expected);
    }

    function test_OperationIdIsNotScenarioIdentity() public pure {
        TimelockScenario memory first = _scenario();
        TimelockScenario memory second = _scenario();

        // The OZ operation hash does not include Timelock address,
        // executor, proposer or Sentinel's selected property.
        second.timelock = address(0xDEAD);
        second.executor = address(0xBEEF);
        second.proposer = address(0xCAFE);
        second.property = TimelockProperty.NOT_READY_EXECUTION_REJECTED;

        assertEq(_timelockOperationId(first), _timelockOperationId(second));
    }
}
