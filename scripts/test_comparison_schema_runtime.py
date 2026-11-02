#!/usr/bin/env python3
"""Positive and negative runtime schema controls."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from validate_comparison_schema import (
    EvidenceSchemaError,
    load_document,
    load_schema,
    validate_document,
)

SCHEMA = load_schema()
DEFS = SCHEMA["$defs"]


def materialize(rule):
    """Build a structurally valid synthetic record.

    Not Solidity-derived evidence; never a replay oracle.
    """

    if "$ref" in rule:
        name = rule["$ref"].split("/")[-1]

        primitives = {
            "address": "0x" + "11" * 20,
            "bytes32": "0x" + "22" * 32,
            "bytes": "0x",
            "uint256": "0",
            "sha": "a" * 40,
            "sha256": "b" * 64,
        }

        if name in primitives:
            return primitives[name]

        return materialize(DEFS[name])

    if "const" in rule:
        return rule["const"]

    if "enum" in rule:
        return rule["enum"][0]

    kind = rule.get("type")

    if kind == "boolean":
        return True

    if kind == "object":
        return {
            name: materialize(rule["properties"][name])
            for name in rule.get("required", [])
        }

    if kind == "array":
        return [
            materialize(rule["items"])
            for _ in range(max(rule.get("minItems", 0), 1))
        ]

    if kind == "string":
        return "sample"

    raise AssertionError(f"Unsupported fixture rule: {rule}")


def sample(route):
    branch = next(
        x for x in SCHEMA["oneOf"]
        if x["properties"]["route"]["const"] == route
    )

    return {
        "format": "protocol-sentinel-comparison",
        "schema_version": "1.0",
        "route": route,
        "semantics_version":
            branch["properties"]["semantics_version"]["const"],
        "scenario": materialize(
            branch["properties"]["scenario"]
        ),
        "stages": materialize(
            branch["properties"]["stages"]
        ),
        "comparison": materialize(
            branch["properties"]["comparison"]
        ),
        "environment": materialize(
            SCHEMA["properties"]["environment"]
        ),
        "provenance": materialize(
            SCHEMA["properties"]["provenance"]
        ),
    }


class ComparisonRuntimeTests(unittest.TestCase):
    def valid(self, document):
        self.assertTrue(validate_document(document, SCHEMA))

    def invalid(self, document):
        with self.assertRaises(EvidenceSchemaError):
            validate_document(document, SCHEMA)

    def test_both_route_fixtures_are_structurally_valid(self):
        for route in (
            "DIRECT_EOA_UUPS",
            "OZ_TIMELOCK_SINGLE",
        ):
            with self.subTest(route=route):
                self.valid(sample(route))

    def test_optional_build_provenance(self):
        for route in (
            "DIRECT_EOA_UUPS",
            "OZ_TIMELOCK_SINGLE",
        ):
            doc = sample(route)

            # Historical Evidence 1.0 is still accepted.
            self.valid(doc)

            doc["provenance"]["buildProvenance"] = {
                "format": "protocol-sentinel-build-provenance-v1",
                "manifestPath": "build/build-provenance.json",
                "manifestSha256": "a" * 64,
            }

            self.valid(doc)

            # The new extension is strict when present.
            del doc["provenance"]["buildProvenance"][
                "manifestSha256"
            ]

            self.invalid(doc)

    def test_missing_required_observation_field(self):
        for route, field in (
            ("DIRECT_EOA_UUPS", "target"),
            ("OZ_TIMELOCK_SINGLE", "executorEOAObserved"),
        ):
            doc = sample(route)
            del doc["stages"]["before"]["observation"][field]
            self.invalid(doc)

    def test_extra_nested_field(self):
        doc = sample("DIRECT_EOA_UUPS")
        doc["stages"]["after"]["observation"]["invented"] = True
        self.invalid(doc)

    def test_wrong_route_semantics_pair(self):
        doc = sample("DIRECT_EOA_UUPS")
        doc["route"] = "OZ_TIMELOCK_SINGLE"
        self.invalid(doc)

    def test_unknown_semantics_version(self):
        doc = sample("OZ_TIMELOCK_SINGLE")
        doc["semantics_version"] = "future-v99"
        self.invalid(doc)

    def test_unknown_enum(self):
        doc = sample("OZ_TIMELOCK_SINGLE")
        doc["scenario"]["spec"]["property"] = "INVALID"
        self.invalid(doc)

    def test_boolean_cannot_be_string(self):
        doc = sample("OZ_TIMELOCK_SINGLE")
        doc["stages"]["before"]["observation"][
            "executorEOAObserved"
        ] = "false"
        self.invalid(doc)

    def test_invalid_address_width(self):
        doc = sample("DIRECT_EOA_UUPS")
        doc["scenario"]["spec"]["actor"] = "0x1234"
        self.invalid(doc)

    def test_uint256_overflow(self):
        doc = sample("OZ_TIMELOCK_SINGLE")
        doc["stages"]["before"]["observation"][
            "readyAt"
        ] = str(1 << 256)
        self.invalid(doc)

    def test_noncanonical_decimal(self):
        doc = sample("OZ_TIMELOCK_SINGLE")
        doc["stages"]["before"]["observation"][
            "readyAt"
        ] = "0001"
        self.invalid(doc)

    def test_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "duplicate.json"
            path.write_text('{"route":"x","route":"y"}')

            with self.assertRaises(EvidenceSchemaError):
                load_document(path)

    def test_nonstandard_json_constant(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "nan.json"
            path.write_text('{"value":NaN}')

            with self.assertRaises(EvidenceSchemaError):
                load_document(path)

    def test_direct_actor_mismatch_is_valid_schema(self):
        doc = sample("DIRECT_EOA_UUPS")

        doc["stages"]["before"]["observation"]["actor"] = (
            "0x" + "33" * 20
        )

        self.valid(doc)

    def test_routed_operation_id_mismatch_is_valid_schema(self):
        doc = sample("OZ_TIMELOCK_SINGLE")

        doc["stages"]["before"]["observation"]["operationId"] = (
            "0x" + "44" * 32
        )

        self.valid(doc)

    def test_missing_eoa_evidence_is_valid_schema(self):
        doc = sample("OZ_TIMELOCK_SINGLE")

        doc["stages"]["before"]["observation"][
            "executorEOAObserved"
        ] = False

        self.valid(doc)

    def test_changed_derived_value_is_schema_valid(self):
        doc = sample("DIRECT_EOA_UUPS")

        doc["scenario"]["derived"]["canonicalCalldata"] = (
            "0xdeadbeef"
        )

        # The independent replay will reject incorrect
        # derived declarations; the schema only checks type.
        self.valid(doc)

    def test_hex_case_and_upper_storage_bits(self):
        doc = sample("DIRECT_EOA_UUPS")

        doc["scenario"]["spec"]["actor"] = (
            "0x" + "AA" * 20
        )

        doc["stages"]["before"]["observation"][
            "implementationBefore"
        ] = "0x" + "FF" * 12 + "11" * 20

        self.valid(doc)

    def test_fork_requires_block_context(self):
        doc = sample("OZ_TIMELOCK_SINGLE")
        doc["environment"]["executionMode"] = "fork"
        self.invalid(doc)

        doc["environment"]["fork"] = {
            "blockNumber": "123",
            "blockHash": "0x" + "55" * 32,
        }

        self.valid(doc)

    def test_local_fixture_rejects_fork_context(self):
        doc = sample("DIRECT_EOA_UUPS")
        doc["environment"]["fork"] = {
            "blockNumber": "123",
            "blockHash": "0x" + "55" * 32,
        }
        self.invalid(doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
