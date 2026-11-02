#!/usr/bin/env python3
"""Generate frozen comparison evidence JSON Schema 2020-12."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "evidence/semantics/registry.json"
DEST = ROOT / "evidence/schema/comparison-1.0.schema.json"

DIRECT_SPEC = [
    ("actor", "address"),
    ("target", "address"),
    ("candidate", "address"),
    ("expectedRevert", "bytes"),
    ("policy", "UpgradePolicy"),
]

ROUTED_SPEC = [
    ("timelock", "address"),
    ("proposer", "address"),
    ("executor", "address"),
    ("proxyAdmin", "address"),
    ("proxy", "address"),
    ("candidate", "address"),
    ("predecessor", "bytes32"),
    ("salt", "bytes32"),
    ("property", "TimelockProperty"),
]

DIRECT_OBSERVATION = [
    ("actor", "address"),
    ("txOrigin", "address"),
    ("target", "address"),
    ("success", "bool"),
    ("returnData", "bytes"),
    ("observedSlot", "bytes32"),
    ("implementationBefore", "bytes32"),
    ("implementationAfter", "bytes32"),
    ("callData", "bytes"),
    ("candidateValidAtObservation", "bool"),
    ("targetValidAtObservation", "bool"),
]

ROUTED_OBSERVATION = [
    ("executor", "address"),
    ("txOrigin", "address"),
    ("executorEOAObserved", "bool"),
    ("executorEOAValid", "bool"),
    ("outerTarget", "address"),
    ("outerCallData", "bytes"),
    ("outerSuccess", "bool"),
    ("returnData", "bytes"),
    ("timelock", "address"),
    ("proxyAdmin", "address"),
    ("operationId", "bytes32"),
    ("operationStateBefore", "OperationState"),
    ("operationStateBeforeObserved", "bool"),
    ("operationDoneBefore", "bool"),
    ("operationDoneAfter", "bool"),
    ("predecessor", "bytes32"),
    ("predecessorStateObserved", "bool"),
    ("predecessorDoneBefore", "bool"),
    ("observedTimestamp", "uint256"),
    ("readyAt", "uint256"),
    ("observedSlot", "bytes32"),
    ("implementationBefore", "bytes32"),
    ("implementationAfter", "bytes32"),
    ("proxyCodeObserved", "bool"),
    ("proxyHasCode", "bool"),
    ("candidateCodeObserved", "bool"),
    ("candidateHasCode", "bool"),
    ("proxyAdminOwnershipObserved", "bool"),
    ("proxyAdminOwnedByTimelock", "bool"),
    ("executorRolesObserved", "bool"),
    ("executorHasRole", "bool"),
    ("openExecutorRole", "bool"),
]


def ref(name):
    return {"$ref": f"#/$defs/{name}"}


def obj(properties, optional=()):
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            key for key in properties if key not in optional
        ],
        "properties": properties,
    }


def text():
    return {"type": "string", "minLength": 1}


def make_fields(fields, enums):
    types = {
        "address": ref("address"),
        "bytes32": ref("bytes32"),
        "bytes": ref("bytes"),
        "uint256": ref("uint256"),
        "bool": {"type": "boolean"},
    }

    result = {}

    for name, kind in fields:
        if kind in types:
            result[name] = types[kind]
        else:
            if kind not in enums:
                raise ValueError(f"Unknown Solidity enum: {kind}")
            result[name] = {"enum": enums[kind]}

    return obj(result)


def make_stage(observation, status, reason):
    return obj({
        "expectedActiveImplementation": ref("address"),
        "observation": observation,
        "evaluation": obj({
            "status": {"enum": status},
            "reason": {"enum": reason},
        }),
    })


def make_comparison(verdicts, reasons):
    return obj({
        "scenarioKey": ref("bytes32"),
        "verdict": {"enum": verdicts},
        "reason": {"enum": reasons},
    })


def build():
    registry = json.loads(REGISTRY.read_text())

    direct = registry["routes"]["DIRECT_EOA_UUPS"]
    routed = registry["routes"]["OZ_TIMELOCK_SINGLE"]

    de = direct["enums"]
    re = routed["enums"]

    # ERROR is not a completed stage evaluation.
    completed_statuses = [
        name for name in de["PolicyStatus"]
        if name != "ERROR"
    ]

    defs = {
        "address": {
            "type": "string",
            "pattern": "^0x[0-9a-fA-F]{40}$",
        },
        "bytes32": {
            "type": "string",
            "pattern": "^0x[0-9a-fA-F]{64}$",
        },
        "bytes": {
            "type": "string",
            "pattern": "^0x(?:[0-9a-fA-F]{2})*$",
        },
        "uint256": {
            "type": "string",
            "pattern": "^(0|[1-9][0-9]*)$",
            "maxLength": 78,
            "description": (
                "Canonical decimal uint256; exact numeric "
                "upper bound checked by the parser."
            ),
        },
        "sha": {
            "type": "string",
            "pattern": "^[0-9a-f]{40}$",
        },
        "sha256": {
            "type": "string",
            "pattern": "^[0-9a-fA-F]{64}$",
        },
    }

    defs["directSpec"] = make_fields(DIRECT_SPEC, de)
    defs["routedSpec"] = make_fields(ROUTED_SPEC, re)

    defs["directObservation"] = make_fields(
        DIRECT_OBSERVATION, de
    )
    defs["routedObservation"] = make_fields(
        ROUTED_OBSERVATION, re
    )

    defs["directScenario"] = obj({
        "scenarioId": ref("bytes32"),
        "spec": ref("directSpec"),
        "derived": obj({
            "canonicalCalldata": ref("bytes"),
        }),
    })

    defs["routedScenario"] = obj({
        "scenarioId": ref("bytes32"),
        "spec": ref("routedSpec"),
        "derived": obj({
            "innerCalldata": ref("bytes"),
            "outerCalldata": ref("bytes"),
            "operationId": ref("bytes32"),
        }),
    })

    defs["directStage"] = make_stage(
        ref("directObservation"),
        completed_statuses,
        de["PolicyReason"],
    )

    defs["routedStage"] = make_stage(
        ref("routedObservation"),
        completed_statuses,
        re["RoutedReason"],
    )

    defs["directStages"] = obj({
        "before": ref("directStage"),
        "after": ref("directStage"),
    })

    defs["routedStages"] = obj({
        "before": ref("routedStage"),
        "after": ref("routedStage"),
    })

    defs["directComparison"] = make_comparison(
        de["ComparisonVerdict"],
        de["ComparisonReason"],
    )

    defs["routedComparison"] = make_comparison(
        de["ComparisonVerdict"],
        re["RoutedComparisonReason"],
    )

    dependencies = obj({
        "openzeppelinContracts": ref("sha"),
        "openzeppelinContractsUpgradeable": ref("sha"),
    })

    fork = obj({
        "blockNumber": ref("uint256"),
        "blockHash": ref("bytes32"),
    })

    environment = obj({
        "fixtureId": text(),
        "executionMode": {
            "enum": ["local_fixture", "fork"],
        },
        "chainId": ref("uint256"),
        "forgeVersion": text(),
        "solcVersion": text(),
        "dependencyRevisions": dependencies,
        "fork": fork,
    }, optional=("fork",))

    environment["allOf"] = [
        {
            "if": {
                "properties": {
                    "executionMode": {"const": "fork"},
                },
                "required": ["executionMode"],
            },
            "then": {"required": ["fork"]},
        },
        {
            "if": {
                "properties": {
                    "executionMode": {"const": "local_fixture"},
                },
                "required": ["executionMode"],
            },
            "then": {"not": {"required": ["fork"]}},
        },
    ]

    defs["environment"] = environment

    defs["provenance"] = obj({
        "repository": text(),
        "sourceCommit": ref("sha"),
        "workingTreeClean": {"type": "boolean"},
        "runId": text(),
        "sourceInputs": {
            "type": "array",
            "minItems": 1,
            "items": obj({
                "path": text(),
                "sha256": ref("sha256"),
            }),
        },
        "reproduceCommand": text(),
    })

    routes = []

    for name, route, scenario, stages, comparison in [
        (
            "DIRECT_EOA_UUPS",
            direct,
            "directScenario",
            "directStages",
            "directComparison",
        ),
        (
            "OZ_TIMELOCK_SINGLE",
            routed,
            "routedScenario",
            "routedStages",
            "routedComparison",
        ),
    ]:
        routes.append({
            "type": "object",
            "required": [
                "route",
                "semantics_version",
                "scenario",
                "stages",
                "comparison",
            ],
            "properties": {
                "route": {"const": name},
                "semantics_version": {
                    "const": route["semanticsVersion"]
                },
                "scenario": ref(scenario),
                "stages": ref(stages),
                "comparison": ref(comparison),
            },
        })

    schema = obj({
        "format": {
            "const": registry["format"],
        },
        "schema_version": {
            "const": registry["schemaVersion"],
        },
        "route": {"type": "string"},
        "semantics_version": {"type": "string"},
        "scenario": {"type": "object"},
        "stages": {"type": "object"},
        "comparison": {"type": "object"},
        "environment": ref("environment"),
        "provenance": ref("provenance"),
    })

    schema.update({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Protocol Sentinel Comparison Evidence 1.0",
        "description": (
            "Strict structural schema. Semantic equivalence "
            "and execution provenance require separate checks."
        ),
        "$defs": defs,
        "oneOf": routes,
    })

    return schema


def main():
    parser = argparse.ArgumentParser()
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--write", action="store_true")
    actions.add_argument("--check", action="store_true")
    args = parser.parse_args()

    data = json.dumps(
        build(),
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    if args.write:
        DEST.parent.mkdir(parents=True, exist_ok=True)
        DEST.write_text(data)
        print("WRITE |", DEST.relative_to(ROOT))
    else:
        if not DEST.is_file() or DEST.read_text() != data:
            raise SystemExit("FAIL | Generated schema is out of sync")
        print("PASS | Generated schema is current")


if __name__ == "__main__":
    main()
