// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ComparativeAuthorityProbe} from "./ComparativeAuthorityProbe.sol";

import {TimelockController} from "@openzeppelin/contracts/governance/TimelockController.sol";

import {ProxyAdmin, ITransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

/// @notice Declared OpenZeppelin single-operation Timelock route.
/// @dev Phase B: direct EOA APIs remain unchanged.
abstract contract TimelockAuthorityProbe is ComparativeAuthorityProbe {
    bytes32 internal constant TIMELOCK_ROUTE_DOMAIN = keccak256("protocol-sentinel/oz-timelock-single/v1");

    enum TimelockProperty {
        READY_UPGRADE_SUCCEEDS,
        NOT_READY_EXECUTION_REJECTED
    }

    /// @notice Caller-supplied scenario specification.
    /// @dev Proposer is preparation context, not proven schedule provenance.
    struct TimelockScenario {
        address timelock;
        address proposer;
        address executor;
        address proxyAdmin;
        address proxy;
        address candidate;
        bytes32 predecessor;
        bytes32 salt;
        TimelockProperty property;
    }

    /// @notice Evidence captured for one routed execution attempt.
    /// @dev These fields do not authenticate their own provenance.
    struct RoutedObservation {
        // Declared execution context observed by the runner.
        address executor;
        address txOrigin;
        bool executorEOAObserved;
        bool executorEOAValid;
        address outerTarget;
        bytes outerCallData;

        // Outer execution result.
        bool outerSuccess;
        bytes returnData;

        // Route and operation identity.
        address timelock;
        address proxyAdmin;
        bytes32 operationId;

        // Timelock state.
        TimelockController.OperationState operationStateBefore;
        bool operationStateBeforeObserved;
        bool operationDoneBefore;
        bool operationDoneAfter;

        // Dependency state.
        bytes32 predecessor;
        bool predecessorStateObserved;
        bool predecessorDoneBefore;

        // Timing evidence.
        uint256 observedTimestamp;
        uint256 readyAt;

        // ERC-1967 proxy evidence.
        bytes32 observedSlot;
        bytes32 implementationBefore;
        bytes32 implementationAfter;

        // Pre-execution conditions.
        bool proxyCodeObserved;
        bool proxyHasCode;
        bool candidateCodeObserved;
        bool candidateHasCode;
        bool proxyAdminOwnershipObserved;
        bool proxyAdminOwnedByTimelock;
        bool executorRolesObserved;
        bool executorHasRole;
        bool openExecutorRole;
    }

    /// @notice Canonical ProxyAdmin action.
    /// @dev No arbitrary initializer calldata in v0.4-B.
    function _timelockUpgradePayload(TimelockScenario memory spec) internal pure returns (bytes memory) {
        return abi.encodeCall(
            ProxyAdmin.upgradeAndCall, (ITransparentUpgradeableProxy(spec.proxy), spec.candidate, bytes(""))
        );
    }

    /// @notice Hash the exact Timelock operation tuple.
    /// @dev Mirrors pinned OZ hashOperation for a zero-value call.
    function _timelockOperationId(TimelockScenario memory spec) internal pure returns (bytes32) {
        return
            keccak256(
                abi.encode(spec.proxyAdmin, uint256(0), _timelockUpgradePayload(spec), spec.predecessor, spec.salt)
            );
    }

    /// @notice Canonical outer Timelock execute calldata.
    function _timelockExecutePayload(TimelockScenario memory spec) internal pure returns (bytes memory) {
        return abi.encodeCall(
            TimelockController.execute,
            (spec.proxyAdmin, uint256(0), _timelockUpgradePayload(spec), spec.predecessor, spec.salt)
        );
    }

    enum RoutedReason {
        NONE,
        CONTEXT_MISMATCH,
        INCOMPLETE_EVIDENCE,
        INCONSISTENT_TIMING,
        INCONSISTENT_EXECUTION,
        UNEXPECTED_REVERT,
        EXECUTION_REJECTED,
        MISSING_UPGRADE_EFFECT
    }

    enum PreparationFailure {
        WRONG_OPERATION_STATE,
        INELIGIBLE_EXECUTOR,
        UNFINISHED_PREDECESSOR,
        INVALID_PROXY_ADMIN,
        INVALID_PROXY,
        INVALID_CANDIDATE,
        NO_IMPLEMENTATION_CHANGE,
        INVALID_EOA_EXECUTOR
    }

    struct RoutedEvaluation {
        PolicyStatus status;
        RoutedReason reason;
    }

    error InvalidTimelockPreparation(PreparationFailure failure);

    function _routeDecision(PolicyStatus status, RoutedReason reason) internal pure returns (RoutedEvaluation memory) {
        return RoutedEvaluation({status: status, reason: reason});
    }

    /// @notice Evaluate a declared routed execution from supplied evidence.
    /// @dev Pure evaluation cannot authenticate observation provenance.
    function _evaluateTimelockRoute(TimelockScenario memory spec, RoutedObservation memory obs)
        internal
        pure
        returns (RoutedEvaluation memory)
    {
        // The complete outer call and operation must match the scenario.
        if (
            obs.executor != spec.executor || obs.txOrigin != spec.executor || obs.outerTarget != spec.timelock
                || obs.timelock != spec.timelock || obs.proxyAdmin != spec.proxyAdmin
                || obs.predecessor != spec.predecessor || obs.operationId != _timelockOperationId(spec)
                || obs.observedSlot != ERC1967_IMPL_SLOT
                || keccak256(obs.outerCallData) != keccak256(_timelockExecutePayload(spec))
        ) {
            return _routeDecision(PolicyStatus.UNKNOWN, RoutedReason.CONTEXT_MISMATCH);
        }

        // Missing evidence must never default to PASS.
        if (
            !obs.operationStateBeforeObserved || !obs.executorEOAObserved || !obs.proxyCodeObserved
                || !obs.candidateCodeObserved || !obs.proxyAdminOwnershipObserved || !obs.executorRolesObserved
                || (spec.predecessor != bytes32(0) && !obs.predecessorStateObserved)
        ) {
            return _routeDecision(PolicyStatus.UNKNOWN, RoutedReason.INCOMPLETE_EVIDENCE);
        }

        TimelockController.OperationState state = obs.operationStateBefore;

        // Validate state against the timestamp semantics of OZ 5.x.
        if (
            (state == TimelockController.OperationState.Waiting
                    && (obs.readyAt <= obs.observedTimestamp || obs.readyAt <= 1))
                || (state == TimelockController.OperationState.Ready
                    && (obs.readyAt > obs.observedTimestamp || obs.readyAt <= 1))
                || (state == TimelockController.OperationState.Unset && obs.readyAt != 0)
                || (state == TimelockController.OperationState.Done && obs.readyAt != 1)
        ) {
            return _routeDecision(PolicyStatus.UNKNOWN, RoutedReason.INCONSISTENT_TIMING);
        }

        if (obs.operationDoneBefore != (state == TimelockController.OperationState.Done)) {
            return _routeDecision(PolicyStatus.UNKNOWN, RoutedReason.INCONSISTENT_EXECUTION);
        }

        TimelockController.OperationState requiredState = spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS
            ? TimelockController.OperationState.Ready
            : TimelockController.OperationState.Waiting;

        if (state != requiredState) {
            revert InvalidTimelockPreparation(PreparationFailure.WRONG_OPERATION_STATE);
        }

        // Address shape is part of the declared EOA model.
        // A pure evaluator trusts the observer's code check.
        if (spec.executor == address(0) || !obs.executorEOAValid) {
            revert InvalidTimelockPreparation(PreparationFailure.INVALID_EOA_EXECUTOR);
        }

        // These are preparation failures, not violations of the policy.
        if (!(obs.executorHasRole || obs.openExecutorRole)) {
            revert InvalidTimelockPreparation(PreparationFailure.INELIGIBLE_EXECUTOR);
        }

        if (spec.predecessor != bytes32(0) && !obs.predecessorDoneBefore) {
            revert InvalidTimelockPreparation(PreparationFailure.UNFINISHED_PREDECESSOR);
        }

        if (!obs.proxyAdminOwnedByTimelock) {
            revert InvalidTimelockPreparation(PreparationFailure.INVALID_PROXY_ADMIN);
        }

        if (!obs.proxyHasCode || address(uint160(uint256(obs.implementationBefore))) == address(0)) {
            revert InvalidTimelockPreparation(PreparationFailure.INVALID_PROXY);
        }

        if (!obs.candidateHasCode) {
            revert InvalidTimelockPreparation(PreparationFailure.INVALID_CANDIDATE);
        }

        address activeBefore = address(uint160(uint256(obs.implementationBefore)));

        address activeAfter = address(uint160(uint256(obs.implementationAfter)));

        if (spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS && activeBefore == spec.candidate) {
            revert InvalidTimelockPreparation(PreparationFailure.NO_IMPLEMENTATION_CHANGE);
        }

        // Pinned TimelockController.execute() has no return value.
        // Nonempty successful return data contradicts this route ABI.
        if (obs.outerSuccess && obs.returnData.length != 0) {
            return _routeDecision(PolicyStatus.UNKNOWN, RoutedReason.INCONSISTENT_EXECUTION);
        }

        // A reverted EVM call cannot retain a state change.
        if (!obs.outerSuccess) {
            if (obs.operationDoneAfter || activeAfter != activeBefore) {
                return _routeDecision(PolicyStatus.UNKNOWN, RoutedReason.INCONSISTENT_EXECUTION);
            }

            if (spec.property == TimelockProperty.READY_UPGRADE_SUCCEEDS) {
                return _routeDecision(PolicyStatus.FAIL, RoutedReason.EXECUTION_REJECTED);
            }

            // Exact pinned OZ 5.x time-state rejection.
            bytes memory expected = abi.encodeWithSelector(
                TimelockController.TimelockUnexpectedOperationState.selector,
                _timelockOperationId(spec),
                bytes32(uint256(4))
            );

            if (keccak256(obs.returnData) == keccak256(expected)) {
                return _routeDecision(PolicyStatus.PASS, RoutedReason.NONE);
            }

            return _routeDecision(PolicyStatus.UNKNOWN, RoutedReason.UNEXPECTED_REVERT);
        }

        // Successful Timelock.execute must mark the operation Done.
        if (!obs.operationDoneAfter) {
            return _routeDecision(PolicyStatus.UNKNOWN, RoutedReason.INCONSISTENT_EXECUTION);
        }

        if (spec.property == TimelockProperty.NOT_READY_EXECUTION_REJECTED) {
            // A Waiting operation executed despite the delay.
            return _routeDecision(PolicyStatus.FAIL, RoutedReason.NONE);
        }

        if (activeAfter != spec.candidate) {
            return _routeDecision(PolicyStatus.FAIL, RoutedReason.MISSING_UPGRADE_EFFECT);
        }

        return _routeDecision(PolicyStatus.PASS, RoutedReason.NONE);
    }

    bytes32 internal constant ERC1967_ADMIN_SLOT = 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103;

    /// @notice Observe one explicitly prepared OZ Timelock operation.
    /// @dev Never schedules, grants permissions or advances EVM time.
    /// @dev Executor/origin fields reflect the configured Foundry prank;
    ///      they are not independent execution attestations.
    function _observeIsolatedTimelockRoute(TimelockScenario memory spec)
        internal
        returns (RoutedObservation memory obs)
    {
        // Foundry prank cannot establish control of a contract account.
        // Reject zero and deployed-code executors before any execution.
        // No-code does not independently prove private-key ownership.
        bool executorEOAValid = spec.executor != address(0) && spec.executor.code.length == 0;

        if (!executorEOAValid) {
            revert InvalidTimelockPreparation(PreparationFailure.INVALID_EOA_EXECUTOR);
        }

        require(spec.timelock.code.length > 0, "Sentinel: missing Timelock");
        require(spec.proxyAdmin.code.length > 0, "Sentinel: missing ProxyAdmin");

        TimelockController controller = TimelockController(payable(spec.timelock));

        ProxyAdmin admin = ProxyAdmin(spec.proxyAdmin);

        bytes32 adminSlotBefore = vm.load(spec.proxy, ERC1967_ADMIN_SLOT);

        // Conservative topology check for our controlled OZ fixture.
        // This slot alone is not proof of the immutable proxy admin.
        require(address(uint160(uint256(adminSlotBefore))) == spec.proxyAdmin, "Sentinel: ProxyAdmin slot mismatch");

        address ownerBefore = admin.owner();

        bytes32 id = _timelockOperationId(spec);

        obs.executor = spec.executor;
        obs.txOrigin = spec.executor;
        obs.executorEOAObserved = true;
        obs.executorEOAValid = executorEOAValid;
        obs.outerTarget = spec.timelock;
        obs.outerCallData = _timelockExecutePayload(spec);

        obs.timelock = spec.timelock;
        obs.proxyAdmin = spec.proxyAdmin;
        obs.operationId = id;

        obs.operationStateBefore = controller.getOperationState(id);

        obs.operationStateBeforeObserved = true;
        obs.operationDoneBefore = controller.isOperationDone(id);

        obs.predecessor = spec.predecessor;

        if (spec.predecessor != bytes32(0)) {
            obs.predecessorStateObserved = true;
            obs.predecessorDoneBefore = controller.isOperationDone(spec.predecessor);
        }

        obs.observedTimestamp = vm.getBlockTimestamp();
        obs.readyAt = controller.getTimestamp(id);

        obs.observedSlot = ERC1967_IMPL_SLOT;

        obs.implementationBefore = vm.load(spec.proxy, ERC1967_IMPL_SLOT);

        obs.proxyCodeObserved = true;
        obs.proxyHasCode = spec.proxy.code.length > 0;

        obs.candidateCodeObserved = true;
        obs.candidateHasCode = spec.candidate.code.length > 0;

        obs.proxyAdminOwnershipObserved = true;
        obs.proxyAdminOwnedByTimelock = ownerBefore == spec.timelock;

        obs.executorRolesObserved = true;

        bytes32 executorRole = controller.EXECUTOR_ROLE();

        obs.executorHasRole = controller.hasRole(executorRole, spec.executor);

        obs.openExecutorRole = controller.hasRole(executorRole, address(0));

        // Preparation is already complete at this snapshot boundary.
        uint256 snapshotId = vm.snapshotState();

        // Only the initiating EOA is impersonated.
        // Timelock -> ProxyAdmin -> proxy calls are real EVM calls.
        vm.prank(spec.executor, spec.executor);

        (obs.outerSuccess, obs.returnData) = spec.timelock.call(obs.outerCallData);

        obs.operationDoneAfter = controller.isOperationDone(id);

        obs.implementationAfter = vm.load(spec.proxy, ERC1967_IMPL_SLOT);

        bool restored = vm.revertToStateAndDelete(snapshotId);

        require(restored, "Sentinel: routed snapshot restore failed");

        // Verify the relevant persistent state was restored.
        require(
            vm.load(spec.proxy, ERC1967_IMPL_SLOT) == obs.implementationBefore, "Sentinel: implementation not restored"
        );

        require(vm.load(spec.proxy, ERC1967_ADMIN_SLOT) == adminSlotBefore, "Sentinel: admin slot not restored");

        require(controller.getOperationState(id) == obs.operationStateBefore, "Sentinel: operation state not restored");

        require(controller.getTimestamp(id) == obs.readyAt, "Sentinel: operation timestamp not restored");

        require(
            controller.isOperationDone(id) == obs.operationDoneBefore, "Sentinel: operation completion not restored"
        );

        require(admin.owner() == ownerBefore, "Sentinel: ProxyAdmin ownership not restored");

        require(
            controller.hasRole(executorRole, spec.executor) == obs.executorHasRole,
            "Sentinel: executor role not restored"
        );

        require(
            controller.hasRole(executorRole, address(0)) == obs.openExecutorRole,
            "Sentinel: open executor role not restored"
        );

        if (spec.predecessor != bytes32(0)) {
            require(
                controller.isOperationDone(spec.predecessor) == obs.predecessorDoneBefore,
                "Sentinel: predecessor state not restored"
            );
        }

        require(vm.getBlockTimestamp() == obs.observedTimestamp, "Sentinel: EVM timestamp changed");
    }

    bytes32 internal constant TIMELOCK_COMPARISON_DOMAIN = keccak256("protocol-sentinel/oz-timelock/comparison/v1");

    enum RoutedComparisonReason {
        NONE,
        SCENARIO_MISMATCH,
        STAGE_BINDING_MISMATCH,
        SAME_IMPLEMENTATION_STAGE,
        PREPARATION_MISMATCH,
        INDETERMINATE_POLICY
    }

    struct RoutedStage {
        address expectedActiveImplementation;
        RoutedObservation observation;
    }

    struct RoutedComparisonResult {
        bytes32 scenarioKey;
        RoutedEvaluation beforeEvaluation;
        RoutedEvaluation afterEvaluation;
        ComparisonVerdict verdict;
        RoutedComparisonReason reason;
    }

    /// @notice Declared scenario identity, not evidence provenance.
    function _routedScenarioKey(bytes32 scenarioId, TimelockScenario memory spec) internal pure returns (bytes32) {
        return keccak256(
            abi.encode(
                TIMELOCK_COMPARISON_DOMAIN,
                scenarioId,
                spec,
                _timelockOperationId(spec),
                _timelockExecutePayload(spec),
                ERC1967_IMPL_SLOT
            )
        );
    }

    function _matchesRoutedScenario(RoutedObservation memory obs, TimelockScenario memory spec)
        internal
        pure
        returns (bool)
    {
        return obs.executor == spec.executor && obs.txOrigin == spec.executor && obs.outerTarget == spec.timelock
            && obs.timelock == spec.timelock && obs.proxyAdmin == spec.proxyAdmin && obs.predecessor == spec.predecessor
            && obs.operationId == _timelockOperationId(spec) && obs.observedSlot == ERC1967_IMPL_SLOT
            && keccak256(obs.outerCallData) == keccak256(_timelockExecutePayload(spec));
    }

    /// @notice Compare explicitly observed governance preconditions.
    /// @dev Does not attest unrecorded configuration or provenance.
    function _sameRoutedPreparation(
        RoutedObservation memory beforeObs,
        RoutedObservation memory afterObs,
        TimelockScenario memory spec
    ) internal pure returns (bool) {
        // Same operation ID does not prove same scheduling state.
        // A cancelled and rescheduled operation may have a new readyAt.
        if (beforeObs.readyAt != afterObs.readyAt) {
            return false;
        }

        if (beforeObs.executorRolesObserved && afterObs.executorRolesObserved) {
            if (
                beforeObs.executorHasRole != afterObs.executorHasRole
                    || beforeObs.openExecutorRole != afterObs.openExecutorRole
            ) {
                return false;
            }
        }

        if (
            beforeObs.proxyAdminOwnershipObserved && afterObs.proxyAdminOwnershipObserved
                && beforeObs.proxyAdminOwnedByTimelock != afterObs.proxyAdminOwnedByTimelock
        ) {
            return false;
        }

        if (
            spec.predecessor != bytes32(0) && beforeObs.predecessorStateObserved && afterObs.predecessorStateObserved
                && beforeObs.predecessorDoneBefore != afterObs.predecessorDoneBefore
        ) {
            return false;
        }

        return true;
    }

    /// @notice Compare one declared routed property across two stages.
    /// @dev Invalid preparation still reverts in the evaluator.
    /// @dev Both evaluations are retained for comparable and
    ///      incomparable observations, unless evaluation reverts.
    function _compareTimelockRoute(
        bytes32 scenarioId,
        TimelockScenario memory spec,
        RoutedStage memory beforeStage,
        RoutedStage memory afterStage
    ) internal pure returns (RoutedComparisonResult memory result) {
        result.scenarioKey = _routedScenarioKey(scenarioId, spec);

        result.beforeEvaluation = _evaluateTimelockRoute(spec, beforeStage.observation);

        result.afterEvaluation = _evaluateTimelockRoute(spec, afterStage.observation);

        PolicyStatus beforeStatus = result.beforeEvaluation.status;
        PolicyStatus afterStatus = result.afterEvaluation.status;

        if (beforeStatus == PolicyStatus.ERROR || afterStatus == PolicyStatus.ERROR) {
            revert InvalidComparisonPolicyStatus();
        }

        if (
            !_matchesRoutedScenario(beforeStage.observation, spec)
                || !_matchesRoutedScenario(afterStage.observation, spec)
        ) {
            result.verdict = ComparisonVerdict.INCOMPARABLE;
            result.reason = RoutedComparisonReason.SCENARIO_MISMATCH;
            return result;
        }

        address actualBefore = address(uint160(uint256(beforeStage.observation.implementationBefore)));

        address actualAfter = address(uint160(uint256(afterStage.observation.implementationBefore)));

        if (
            actualBefore != beforeStage.expectedActiveImplementation
                || actualAfter != afterStage.expectedActiveImplementation
        ) {
            result.verdict = ComparisonVerdict.INCOMPARABLE;
            result.reason = RoutedComparisonReason.STAGE_BINDING_MISMATCH;
            return result;
        }

        if (beforeStage.expectedActiveImplementation == afterStage.expectedActiveImplementation) {
            result.verdict = ComparisonVerdict.INCOMPARABLE;
            result.reason = RoutedComparisonReason.SAME_IMPLEMENTATION_STAGE;
            return result;
        }

        if (!_sameRoutedPreparation(beforeStage.observation, afterStage.observation, spec)) {
            result.verdict = ComparisonVerdict.INCOMPARABLE;
            result.reason = RoutedComparisonReason.PREPARATION_MISMATCH;
            return result;
        }

        if (beforeStatus == PolicyStatus.UNKNOWN || afterStatus == PolicyStatus.UNKNOWN) {
            result.verdict = ComparisonVerdict.INDETERMINATE;
            result.reason = RoutedComparisonReason.INDETERMINATE_POLICY;
            return result;
        }

        if (beforeStatus == PolicyStatus.PASS) {
            result.verdict = afterStatus == PolicyStatus.PASS
                ? ComparisonVerdict.STILL_SATISFIED
                : ComparisonVerdict.CHANGED_TO_VIOLATION;
        } else {
            result.verdict = afterStatus == PolicyStatus.PASS
                ? ComparisonVerdict.CHANGED_TO_SATISFIED
                : ComparisonVerdict.STILL_VIOLATED;
        }

        result.reason = RoutedComparisonReason.NONE;
    }
}
