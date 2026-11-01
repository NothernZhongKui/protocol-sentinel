// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AuthorityProbe} from "./helpers/AuthorityProbe.sol";
import {VaultV1} from "../src/VaultV1.sol";
import {UpgradeProbe} from "./fixtures/VaultVersions.sol";

import {
    ERC1967Proxy
} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";

contract ReviewSlotIdentityTest is AuthorityProbe {
    bytes32 internal constant WRONG_ADMIN_SLOT =
        0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103;

    function test_WrongSlotMustNotProducePass() public {
        address governor = makeAddr("slot-governor");
        address operator = makeAddr("slot-operator");

        VaultV1 implementation = new VaultV1();
        UpgradeProbe candidate = new UpgradeProbe();

        ERC1967Proxy proxy = new ERC1967Proxy(
            address(implementation),
            abi.encodeCall(
                VaultV1.initialize,
                (governor, operator)
            )
        );

        bytes memory callData = abi.encodeWithSignature(
            "upgradeToAndCall(address,bytes)",
            address(candidate),
            bytes("")
        );

        bytes memory expectedRevert = abi.encodeWithSignature(
            "OwnableUnauthorizedAccount(address)",
            operator
        );

        bytes32 candidateWord =
            bytes32(uint256(uint160(address(candidate))));

        // Control: observe the correct implementation slot.
        Observation memory correct = _observeIsolatedCall(
            operator,
            address(proxy),
            callData,
            ERC1967_IMPL_SLOT
        );

        PolicyStatus correctStatus = _classifyUpgrade(
            correct,
            candidateWord,
            expectedRevert,
            operator,
            address(proxy)
        );

        assertEq(
            uint256(correctStatus),
            uint256(PolicyStatus.PASS)
        );

        // Adversarial case: observe an unrelated storage slot.
        Observation memory wrong = _observeIsolatedCall(
            operator,
            address(proxy),
            callData,
            WRONG_ADMIN_SLOT
        );

        assertFalse(wrong.success);
        assertEq(wrong.returnData, expectedRevert);
        assertEq(wrong.implementationBefore, wrong.implementationAfter);

        PolicyStatus wrongStatus = _classifyUpgrade(
            wrong,
            candidateWord,
            expectedRevert,
            operator,
            address(proxy)
        );

        // Wrong storage identity cannot justify a security PASS.
        assertEq(
            uint256(wrongStatus),
            uint256(PolicyStatus.UNKNOWN),
            "Wrong slot must produce UNKNOWN"
        );
    }
}
