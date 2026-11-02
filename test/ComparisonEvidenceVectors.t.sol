// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {TimelockAuthorityProbe} from "../src/TimelockAuthorityProbe.sol";

contract ComparisonEvidenceVectorsTest is TimelockAuthorityProbe {
    function test_ExportComparisonIdentityVectors() public {
        string memory key = "sentinel_c1_identity_vectors";

        vm.serializeString(key, "format", "protocol-sentinel-identity-v1");

        bytes32 directScenarioId = bytes32(uint256(0x4c01));

        UpgradeCheck memory direct = UpgradeCheck({
            actor: address(0x1001),
            target: address(0x2001),
            candidate: address(0x3001),
            expectedRevert: bytes(""),
            policy: UpgradePolicy.NO_IMPLEMENTATION_REPLACEMENT
        });

        vm.serializeBytes32(key, "direct_scenario_id", directScenarioId);
        vm.serializeAddress(key, "direct_actor", direct.actor);
        vm.serializeAddress(key, "direct_target", direct.target);
        vm.serializeAddress(key, "direct_candidate", direct.candidate);

        vm.serializeBytes(
            key,
            "direct_calldata",
            abi.encodeWithSignature("upgradeToAndCall(address,bytes)", direct.candidate, bytes(""))
        );

        // Exercise both numeric enum ordinals and ABI dynamic
        // byte padding boundaries.
        uint256[5] memory lengths = [uint256(0), uint256(1), uint256(31), uint256(32), uint256(33)];

        for (uint256 policy = 0; policy < 2; ++policy) {
            direct.policy = UpgradePolicy(policy);

            for (uint256 i = 0; i < lengths.length; ++i) {
                uint256 length = lengths[i];
                bytes memory revertData = new bytes(length);

                for (uint256 j = 0; j < length; ++j) {
                    revertData[j] = bytes1(uint8(j + 1));
                }

                direct.expectedRevert = revertData;

                string memory suffix = string.concat(vm.toString(policy), "_", vm.toString(length));

                vm.serializeBytes(key, string.concat("direct_revert_", suffix), revertData);

                vm.serializeBytes32(
                    key, string.concat("direct_key_", suffix), _directScenarioKey(directScenarioId, direct)
                );
            }
        }

        bytes32 routedScenarioId = bytes32(uint256(0x4c02));

        TimelockScenario memory routed = TimelockScenario({
            timelock: address(0x4001),
            proposer: address(0x4002),
            executor: address(0x4003),
            proxyAdmin: address(0x5001),
            proxy: address(0x5002),
            candidate: address(0x5003),
            predecessor: bytes32(0),
            salt: bytes32(uint256(0x7777)),
            property: TimelockProperty.READY_UPGRADE_SUCCEEDS
        });

        vm.serializeBytes32(key, "routed_scenario_id", routedScenarioId);

        vm.serializeAddress(key, "routed_timelock", routed.timelock);
        vm.serializeAddress(key, "routed_proposer", routed.proposer);
        vm.serializeAddress(key, "routed_executor", routed.executor);
        vm.serializeAddress(key, "routed_proxy_admin", routed.proxyAdmin);
        vm.serializeAddress(key, "routed_proxy", routed.proxy);
        vm.serializeAddress(key, "routed_candidate", routed.candidate);

        for (uint256 i = 0; i < 2; ++i) {
            routed.predecessor = i == 0 ? bytes32(0) : bytes32(uint256(0x5050));

            routed.property =
                i == 0 ? TimelockProperty.READY_UPGRADE_SUCCEEDS : TimelockProperty.NOT_READY_EXECUTION_REJECTED;

            string memory suffix = vm.toString(i);

            vm.serializeUint(key, string.concat("routed_property_", suffix), uint256(routed.property));

            vm.serializeBytes32(key, string.concat("routed_predecessor_", suffix), routed.predecessor);

            vm.serializeBytes(key, string.concat("routed_inner_", suffix), _timelockUpgradePayload(routed));

            vm.serializeBytes(key, string.concat("routed_outer_", suffix), _timelockExecutePayload(routed));

            vm.serializeBytes32(key, string.concat("routed_operation_id_", suffix), _timelockOperationId(routed));

            vm.serializeBytes32(
                key, string.concat("routed_scenario_key_", suffix), _routedScenarioKey(routedScenarioId, routed)
            );
        }

        // This must be last: the serializer returns the whole object.
        string memory json = vm.serializeBytes32(key, "routed_salt", routed.salt);

        if (vm.envOr("EXPORT_COMPARISON_VECTORS", false)) {
            vm.writeJson(json, "./artifacts/demo/comparison-abi-vectors.json");
        }
    }
}
