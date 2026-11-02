// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AuthorityProbe} from "protocol-sentinel/AuthorityProbe.sol";

contract MockCandidate {
    function proxiableUUID() external pure returns (bytes32) {
        return 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
    }
}

contract MockTarget {
    error NotGovernor(address caller);

    address public immutable governor;
    bool public risky;

    constructor(address initial, address governor_) {
        governor = governor_;

        assembly {
            sstore(
                0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc,
                initial
            )
        }
    }

    function enableRiskyUpgrade() external {
        require(msg.sender == governor, "Not governor");
        risky = true;
    }

    function upgradeToAndCall(address candidate, bytes calldata) external {
        if (!risky && msg.sender != governor) {
            revert NotGovernor(msg.sender);
        }

        assembly {
            sstore(
                0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc,
                candidate
            )
        }
    }
}

contract SentinelConsumerTest is AuthorityProbe {
    function test_ExternalConsumerDetectsRegression() public {
        address operator = address(0xBEEF);

        MockCandidate initial = new MockCandidate();
        MockCandidate candidate = new MockCandidate();

        MockTarget target = new MockTarget(
            address(initial),
            address(this)
        );

        UpgradeCheck memory spec = UpgradeCheck({
            actor: operator,
            target: address(target),
            candidate: address(candidate),
            expectedRevert: abi.encodeWithSelector(
                MockTarget.NotGovernor.selector,
                operator
            ),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });

        UpgradeCheckResult memory baseline = _checkIsolatedUpgrade(spec);

        assertEq(
            uint256(baseline.status),
            uint256(PolicyStatus.PASS)
        );

        target.enableRiskyUpgrade();

        UpgradeCheckResult memory regression = _checkIsolatedUpgrade(spec);

        assertEq(
            uint256(regression.status),
            uint256(PolicyStatus.FAIL)
        );

        assertEq(
            address(uint160(uint256(vm.load(
                address(target),
                ERC1967_IMPL_SLOT
            )))),
            address(initial)
        );
    }
}
