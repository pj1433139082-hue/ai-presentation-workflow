"""Detect changes between validated project inputs and publishing their outputs."""

from __future__ import annotations

import hashlib
import ctypes
import json
import os
from pathlib import Path


def document_snapshot(root: Path, documents: dict, *, virtual_documents: set[str] | None = None) -> dict[Path, str]:
    virtual = virtual_documents or set()
    paths = {root / name for name in documents if name not in virtual}
    expected_hashes = {}
    path_keys = {"path", "output", "source_path", "mask_path", "concept_path", "master_path",
                 "component_master_path", "comparison_path", "image_path", "packet_path",
                 "final_contact_sheet", "exception_register", "deliverable_index", "approved_contentful_path"}
    hash_fields = {"path": "sha256", "output": "sha256", "source_path": "source_sha256",
                   "mask_path": "mask_sha256", "concept_path": "concept_sha256", "master_path": "master_sha256",
                   "component_master_path": "component_master_sha256", "comparison_path": "comparison_sha256",
                   "image_path": "image_sha256", "packet_path": "packet_sha256",
                   "approved_contentful_path": "approved_contentful_sha256", "final_contact_sheet": "contact_sheet_sha256"}

    def expect(path, digest):
        if isinstance(digest, str) and len(digest) == 64:
            if path in expected_hashes and expected_hashes[path] != digest:
                raise ValueError("validated project inputs contain conflicting file hashes")
            expected_hashes[path] = digest

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "approved_artifacts" and isinstance(child, dict) and value.get("status") == "approved":
                    for relative, digest in child.items():
                        if relative not in virtual:
                            path = (root / relative).resolve()
                            paths.add(path)
                            expect(path, digest)
                elif key in path_keys and isinstance(child, str):
                    candidate = (root / child).resolve()
                    if candidate.is_relative_to(root) and candidate.is_file():
                        paths.add(candidate)
                        expect(candidate, value.get(hash_fields.get(key)))
                elif key == "evidence_files" and isinstance(child, list):
                    paths.update(root / relative for relative in child if isinstance(relative, str))
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for name, document in documents.items():
        if name not in virtual and json.loads((root / name).read_text(encoding="utf-8")) != document:
            raise ValueError("project input changed during preflight")
        collect(document)
    snapshot = {}
    for path in paths:
        path = path.resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("qualification refers to a missing or unsafe project input")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if path in expected_hashes and digest != expected_hashes[path]:
            raise ValueError("validated project evidence changed during preflight")
        snapshot[path] = digest
    return snapshot


def assert_current(snapshot: dict[Path, str]) -> None:
    for path, digest in snapshot.items():
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("project input changed while publishing; output is not accepted")


def publish_new_directory(staging: Path, output: Path) -> None:
    if os.name == "nt":
        staging.rename(output)
        return
    native = ctypes.CDLL(None, use_errno=True)
    rename = getattr(native, "renameat2", None)
    if rename is None:
        raise OSError("atomic directory publication without replacement is unavailable")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(staging), -100, os.fsencode(output), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(output))
