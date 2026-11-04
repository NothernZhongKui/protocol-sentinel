#!/usr/bin/env python3
"""Explicit comparison Evidence version selection and workspace verification.

Unknown versions and malformed 1.1 never fall back to the legacy 1.0 reader.
This does not authenticate the EVM execution itself.
"""

import json
from pathlib import Path

from validate_comparison_schema import validate_document

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_10 = ROOT / "evidence/schema/comparison-1.0.schema.json"
SCHEMA_11 = ROOT / "evidence/schema/comparison-1.1.schema.json"


class WorkspaceEvidenceError(ValueError):
    pass


def schema_for(document):
    if not isinstance(document, dict):
        raise WorkspaceEvidenceError("Invalid Evidence document")
    version = document.get("schema_version")
    if type(version) is not str or version not in {"1.0", "1.1"}:
        raise WorkspaceEvidenceError("Unsupported Evidence version")
    path = {"1.0": SCHEMA_10, "1.1": SCHEMA_11}[version]
    return json.loads(path.read_text(encoding="utf-8"))


def validate_versioned(document):
    schema = schema_for(document)
    validate_document(document, schema=schema)
    return schema


def verify_workspace_evidence(document, context, manifest_digest):
    if document.get("schema_version") != "1.1":
        raise WorkspaceEvidenceError("Expected workspace Evidence 1.1")
    validate_versioned(document)
    provenance = document["provenance"]
    expected = {
        "repository": context.repository_root.name,
        "sourceCommit": context.repository_commit,
        "workspace": context.workspace,
        "toolPath": context.tool_path,
        "toolCommit": context.tool_commit,
        "workingTreeClean": True,
    }
    for key, value in expected.items():
        if provenance.get(key) != value:
            raise WorkspaceEvidenceError("Workspace Evidence mismatch: " + key)
    if provenance["buildProvenance"] != {
        "format": "protocol-sentinel-build-provenance-v2",
        "manifestPath": "build/build-provenance.json",
        "manifestSha256": manifest_digest,
    }:
        raise WorkspaceEvidenceError("Workspace build reference mismatch")
    return True
