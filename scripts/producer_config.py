#!/usr/bin/env python3
"""Strict Direct EOA/UUPS producer TOML parser shared by doctor and workspace runner.

Keep this parser equivalent to the legacy v0.5 read_config contract; neither
function accepts candidate-provided policy or makes an authority decision.
"""

import re
import tomllib
from pathlib import Path

IDENT = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
SCENARIO = re.compile(r"0x[0-9a-fA-F]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_config(path):
    document = tomllib.loads(Path(path).read_text(encoding="utf-8"))

    require(
        set(document) == {"sentinel", "producer"},
        "Invalid configuration sections",
    )

    require(
        document["sentinel"] == {
            "config_version": "1",
            "route": "DIRECT_EOA_UUPS",
        },
        "Unsupported Sentinel configuration",
    )

    producer = document["producer"]
    required = {
        "id",
        "contract",
        "test",
        "source",
        "fixture_id",
        "scenario_id",
    }

    require(
        isinstance(producer, dict) and set(producer) == required,
        "Invalid producer configuration",
    )

    for field in ("id", "contract", "test"):
        value = producer[field]
        require(
            isinstance(value, str) and IDENT.fullmatch(value),
            f"Invalid producer {field}",
        )

    require(
        producer["test"].startswith("test_"),
        "Not a Foundry test",
    )

    fixture = producer["fixture_id"]
    require(
        isinstance(fixture, str) and 0 < len(fixture) <= 128,
        "Invalid fixture ID",
    )

    scenario = producer["scenario_id"]
    require(
        isinstance(scenario, str) and SCENARIO.fullmatch(scenario),
        "Invalid scenario ID",
    )

    source = producer["source"]
    require(
        isinstance(source, str),
        "Invalid producer source",
    )

    relative = Path(source)
    require(
        not relative.is_absolute()
        and ".." not in relative.parts
        and source.startswith("test/")
        and source.endswith(".sol"),
        "Unsafe producer source path",
    )

    return producer
