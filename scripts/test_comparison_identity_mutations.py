#!/usr/bin/env python3
"""Adversarial tests for Solidity/Python golden identity vectors."""

import copy
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from check_comparison_identity_vectors import (
    GOLDEN,
    hexbytes,
    strict_json,
    verify_all,
)

BASELINE = strict_json(GOLDEN.read_text(encoding="utf-8"))


def changed_hex(value):
    raw = bytearray(hexbytes(value))

    if not raw:
        return "0x01"

    raw[-1] ^= 1
    return "0x" + raw.hex()


def mutate(field, value):
    result = copy.deepcopy(BASELINE)
    result[field] = value
    return result


class IdentityVectorMutationTests(unittest.TestCase):
    def verify_silently(self, document):
        with redirect_stdout(io.StringIO()):
            verify_all(document)

    def test_unchanged_golden_vectors_pass(self):
        self.verify_silently(copy.deepcopy(BASELINE))

    def test_identity_and_payload_mutations_are_detected(self):
        cases = {
            "direct scenario ID": (
                "direct_scenario_id",
                changed_hex(BASELINE["direct_scenario_id"]),
            ),
            "direct actor": (
                "direct_actor",
                "0x" + "ff" * 20,
            ),
            "direct target": (
                "direct_target",
                "0x" + "ff" * 20,
            ),
            "direct candidate": (
                "direct_candidate",
                "0x" + "ff" * 20,
            ),
            "direct canonical calldata": (
                "direct_calldata",
                changed_hex(BASELINE["direct_calldata"]),
            ),
            "direct revert payload": (
                "direct_revert_0_31",
                changed_hex(BASELINE["direct_revert_0_31"]),
            ),
            "direct scenario key": (
                "direct_key_1_33",
                changed_hex(BASELINE["direct_key_1_33"]),
            ),
            "routed scenario ID": (
                "routed_scenario_id",
                changed_hex(BASELINE["routed_scenario_id"]),
            ),
            "routed candidate": (
                "routed_candidate",
                "0x" + "ff" * 20,
            ),
            "routed inner calldata": (
                "routed_inner_0",
                changed_hex(BASELINE["routed_inner_0"]),
            ),
            "routed outer calldata": (
                "routed_outer_1",
                changed_hex(BASELINE["routed_outer_1"]),
            ),
            "Timelock operation ID": (
                "routed_operation_id_1",
                changed_hex(BASELINE["routed_operation_id_1"]),
            ),
            "Timelock scenario key": (
                "routed_scenario_key_0",
                changed_hex(BASELINE["routed_scenario_key_0"]),
            ),
            "Timelock salt": (
                "routed_salt",
                changed_hex(BASELINE["routed_salt"]),
            ),
            "Timelock property ordinal": (
                "routed_property_1",
                0,
            ),
            "Timelock predecessor": (
                "routed_predecessor_1",
                changed_hex(BASELINE["routed_predecessor_1"]),
            ),
        }

        for label, (field, value) in cases.items():
            with self.subTest(mutation=label):
                document = mutate(field, value)

                with self.assertRaises(
                    (AssertionError, ValueError)
                ):
                    self.verify_silently(document)

    def test_missing_field_rejected(self):
        document = copy.deepcopy(BASELINE)
        del document["direct_key_0_0"]

        with self.assertRaises(AssertionError):
            self.verify_silently(document)

    def test_unexpected_field_rejected(self):
        document = copy.deepcopy(BASELINE)
        document["unrecognized"] = "value"

        with self.assertRaises(AssertionError):
            self.verify_silently(document)

    def test_invalid_hex_width_rejected(self):
        document = mutate("direct_actor", "0x1234")

        with self.assertRaises(AssertionError):
            self.verify_silently(document)

    def test_hex_whitespace_rejected(self):
        document = mutate(
            "direct_actor",
            "0x" + "11 " * 20,
        )

        with self.assertRaises(AssertionError):
            self.verify_silently(document)

    def test_odd_length_hex_rejected(self):
        document = mutate("direct_actor", "0x123")

        with self.assertRaises(AssertionError):
            self.verify_silently(document)

    def test_duplicate_json_field_rejected(self):
        raw = '{"key":"first","key":"second"}'

        with self.assertRaisesRegex(ValueError, "Duplicate"):
            strict_json(raw)

    def test_nonstandard_json_constant_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid"):
            strict_json('{"value":NaN}')

    def test_uppercase_hex_preserves_identity(self):
        document = copy.deepcopy(BASELINE)

        document["direct_key_1_33"] = (
            "0x" + BASELINE["direct_key_1_33"][2:].upper()
        )

        document["routed_scenario_key_0"] = (
            "0x" + BASELINE["routed_scenario_key_0"][2:].upper()
        )

        self.verify_silently(document)

    def test_json_key_order_is_irrelevant(self):
        document = dict(reversed(list(BASELINE.items())))
        self.verify_silently(document)

    def test_abi_vectors_are_not_nist_sha3(self):
        from hashlib import sha3_256
        from eth_hash.auto import keccak

        message = b"protocol-sentinel-keccak-control"

        self.assertNotEqual(
            sha3_256(message).digest(),
            keccak(message),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
