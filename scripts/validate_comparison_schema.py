#!/usr/bin/env python3
"""Strict structural validation for comparison evidence 1.0.

Does not authenticate observations or replay classifications.
"""

import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "evidence/schema/comparison-1.0.schema.json"

MAX_FILE_SIZE = 4 * 1024 * 1024
UINT256_MAX = (1 << 256) - 1


class EvidenceSchemaError(ValueError):
    pass


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceSchemaError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def invalid_constant(value):
    raise EvidenceSchemaError(f"Invalid JSON constant: {value}")


def load_document(path):
    path = Path(path)

    if path.stat().st_size > MAX_FILE_SIZE:
        raise EvidenceSchemaError("Evidence exceeds size limit")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_keys,
        parse_constant=invalid_constant,
    )


def load_schema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def check_lexical(value, rule, definitions, location="$"):
    """Enforce full-string lexical matching and uint256 bounds."""

    if "$ref" in rule:
        prefix = "#/$defs/"
        target = rule["$ref"]

        if not target.startswith(prefix):
            raise EvidenceSchemaError("Unsupported schema reference")

        definition = target[len(prefix):]
        check_lexical(
            value, definitions[definition], definitions, location
        )
        return

    if rule.get("type") == "object":
        for name, child in rule.get("properties", {}).items():
            if name in value:
                check_lexical(
                    value[name],
                    child,
                    definitions,
                    f"{location}.{name}",
                )
        return

    if rule.get("type") == "array":
        for index, child in enumerate(value):
            check_lexical(
                child,
                rule["items"],
                definitions,
                f"{location}[{index}]",
            )
        return

    if not isinstance(value, str):
        return

    pattern = rule.get("pattern")

    if pattern and re.fullmatch(pattern, value) is None:
        raise EvidenceSchemaError(
            f"Noncanonical lexical value at {location}"
        )

    if rule.get("description", "").startswith(
        "Canonical decimal uint256"
    ):
        if int(value) > UINT256_MAX:
            raise EvidenceSchemaError(
                f"uint256 overflow at {location}"
            )


def validate_document(document, schema=None):
    if schema is None:
        schema = load_schema()

    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(document))

    if errors:
        error = sorted(
            errors,
            key=lambda e: (len(e.absolute_path), str(e.absolute_path))
        )[0]

        location = ".".join(str(x) for x in error.absolute_path)

        raise EvidenceSchemaError(
            f"Invalid comparison evidence at {location or '$'}: "
            f"{error.message}"
        )

    definitions = schema["$defs"]

    # Common fields use the envelope rules.
    for field in ("environment", "provenance"):
        check_lexical(
            document[field],
            schema["properties"][field],
            definitions,
            f"$.{field}",
        )

    # Route-specific fields use exactly one selected branch.
    route = document["route"]

    branch = next(
        item for item in schema["oneOf"]
        if item["properties"]["route"]["const"] == route
    )

    for field in ("scenario", "stages", "comparison"):
        check_lexical(
            document[field],
            branch["properties"][field],
            definitions,
            f"$.{field}",
        )

    return True


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: validate_comparison_schema.py evidence.json"
        )

    try:
        document = load_document(sys.argv[1])
        validate_document(document)
    except (
        EvidenceSchemaError,
        ValueError,
        OSError,
        UnicodeError,
    ) as exc:
        raise SystemExit(f"FAIL | {exc}")

    print("PASS | Comparison evidence schema VALID")
    print("Scope: structural validation only")
    print("Classification replay: NOT_CHECKED")
    print("Execution provenance: UNAUTHENTICATED")


if __name__ == "__main__":
    main()
