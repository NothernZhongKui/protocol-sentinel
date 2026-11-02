#!/usr/bin/env python3
"""Check schema completeness against frozen Solidity structs.

This checks the schema contract, not JSON instances.
Runtime validation and mutation tests follow separately.
"""

import json
import re
from pathlib import Path

from build_comparison_schema import (
    ROOT,
    DEST,
    DIRECT_SPEC,
    DIRECT_OBSERVATION,
    ROUTED_SPEC,
    ROUTED_OBSERVATION,
)

registry = json.loads(
    (ROOT / "evidence/semantics/registry.json").read_text()
)

schema = json.loads(DEST.read_text())
defs = schema["$defs"]

sources = {
    name: (ROOT / name).read_text()
    for name in (
        "src/AuthorityProbe.sol",
        "src/ComparativeAuthorityProbe.sol",
        "src/TimelockAuthorityProbe.sol",
    )
}


def check(value, description):
    assert value, description
    print("PASS |", description)


def solidity_fields(source, name):
    match = re.search(
        r"\bstruct\s+" + re.escape(name) + r"\s*\{([^}]+)\}",
        source,
        re.S,
    )
    assert match, f"Missing Solidity struct {name}"

    fields = re.findall(
        r"^\s*"
        r"(address|bool|bytes32|bytes|uint256|"
        r"UpgradePolicy|TimelockProperty|"
        r"TimelockController\.OperationState)"
        r"\s+(\w+)\s*;",
        match.group(1),
        re.M,
    )

    return [
        (
            field_name,
            "OperationState"
            if field_type == "TimelockController.OperationState"
            else field_type,
        )
        for field_type, field_name in fields
    ]


cases = [
    (
        "directSpec",
        "src/AuthorityProbe.sol",
        "UpgradeCheck",
        DIRECT_SPEC,
    ),
    (
        "directObservation",
        "src/AuthorityProbe.sol",
        "Observation",
        DIRECT_OBSERVATION,
    ),
    (
        "routedSpec",
        "src/TimelockAuthorityProbe.sol",
        "TimelockScenario",
        ROUTED_SPEC,
    ),
    (
        "routedObservation",
        "src/TimelockAuthorityProbe.sol",
        "RoutedObservation",
        ROUTED_OBSERVATION,
    ),
]

for definition, file, struct, expected in cases:
    actual = solidity_fields(sources[file], struct)

    check(
        actual == expected,
        f"Solidity {struct} field names, types and order",
    )

    definition_schema = defs[definition]

    check(
        list(definition_schema["properties"]) ==
        [name for name, _ in expected],
        f"{definition}: exact JSON fields",
    )

    check(
        definition_schema["required"] ==
        [name for name, _ in expected],
        f"{definition}: all fields required",
    )

    check(
        definition_schema["additionalProperties"] is False,
        f"{definition}: no unexpected fields",
    )

check(
    len(DIRECT_OBSERVATION) == 11,
    "Direct observation has 11 required fields",
)

check(
    len(ROUTED_OBSERVATION) == 32,
    "Routed observation has 32 required fields",
)

check(
    set(schema["required"]) == {
        "format",
        "schema_version",
        "route",
        "semantics_version",
        "scenario",
        "stages",
        "comparison",
        "environment",
        "provenance",
    },
    "Exact envelope requirements",
)

check(
    schema["additionalProperties"] is False,
    "Envelope rejects unknown fields",
)

branches = schema["oneOf"]

check(
    len(branches) == 2,
    "Exactly two route schema branches",
)

expected_routes = registry["routes"]

for branch in branches:
    props = branch["properties"]

    route = props["route"]["const"]
    semantics = props["semantics_version"]["const"]

    check(
        semantics == expected_routes[route]["semanticsVersion"],
        f"{route}: frozen semantics discriminator",
    )

check(
    set(defs["directStages"]["required"]) ==
    {"before", "after"},
    "Direct stages are named and required",
)

check(
    set(defs["routedStages"]["required"]) ==
    {"before", "after"},
    "Routed stages are named and required",
)

for name in (
    "directSpec",
    "routedSpec",
    "directObservation",
    "routedObservation",
    "directScenario",
    "routedScenario",
    "directStage",
    "routedStage",
    "directStages",
    "routedStages",
    "directComparison",
    "routedComparison",
    "environment",
    "provenance",
):
    item = defs[name]

    check(
        item.get("additionalProperties") is False
        and set(item["required"]) <= set(item["properties"]),
        f"{name}: strict nested object",
    )

print()
print("COMPARISON SCHEMA CONTRACT: PASS")
print("Scope: structural completeness, not classification replay")
