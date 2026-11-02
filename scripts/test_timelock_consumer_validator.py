#!/usr/bin/env python3

import copy
import unittest

from verify_timelock_consumer_results import (
    ConsumerResultError,
    REQUIRED_TESTS,
    validate_results,
)


class ConsumerValidatorTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "test/SentinelTimelockConsumer.t.sol:"
            "SentinelTimelockConsumerTest": {
                "test_results": {
                    name: {"status": "Success"}
                    for name in REQUIRED_TESTS
                }
            }
        }

    def results(self):
        return next(iter(self.data.values()))["test_results"]

    def test_all_success(self):
        self.assertEqual(
            len(validate_results(self.data)),
            len(REQUIRED_TESTS),
        )

    def test_all_skipped_rejected(self):
        for result in self.results().values():
            result["status"] = "Skipped"

        with self.assertRaises(ConsumerResultError):
            validate_results(self.data)

    def test_one_skipped_rejected(self):
        next(iter(self.results().values()))["status"] = "Skipped"

        with self.assertRaises(ConsumerResultError):
            validate_results(self.data)

    def test_one_missing_rejected(self):
        self.results().pop(next(iter(REQUIRED_TESTS)))

        with self.assertRaises(ConsumerResultError):
            validate_results(self.data)

    def test_one_failed_rejected(self):
        next(iter(self.results().values()))["status"] = "Failure"

        with self.assertRaises(ConsumerResultError):
            validate_results(self.data)

    def test_extra_skipped_rejected(self):
        self.results()["test_Additional()"] = {"status": "Skipped"}

        with self.assertRaises(ConsumerResultError):
            validate_results(self.data)

    def test_empty_suite_rejected(self):
        self.results().clear()

        with self.assertRaises(ConsumerResultError):
            validate_results(self.data)

    def test_missing_suite_rejected(self):
        with self.assertRaises(ConsumerResultError):
            validate_results({})


if __name__ == "__main__":
    unittest.main()
