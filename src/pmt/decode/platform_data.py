"""Validate registry coverage before processing a run."""

import json
from pathlib import Path
import subprocess

from .payload_decoder import PayloadDecoder
from .schema_loader import read_xml


def revision(metadata):
    result = subprocess.run(["git", "-C", str(Path(metadata).resolve().parent), "rev-parse", "HEAD"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def validate(metadata, run_dir=None):
    decoder = PayloadDecoder(metadata)
    if run_dir is not None:
        inventory = json.loads((run_dir / "run.json").read_text())["Inventory"]
        keys = sorted({(int(item["Guid"], 16), int(item["Size"])) for item in inventory})
    else:
        keys = sorted(decoder.registry.entries)
    schemas = []
    mappings = []
    errors = []
    for guid, size in keys:
        files = {}
        stage = "mapping"
        try:
            paths = decoder.registry.select(hex(guid), size)
            files = {kind: str(path) for kind, path in paths.items()}
            for kind in ("aggregator", "aggregatorinterface"):
                if int(read_xml(paths[kind]).findtext("uniqueid"), 16) != guid:
                    raise ValueError(kind + " GUID differs from registry mapping")
            mappings.append({"guid": hex(guid), "size": size, "files": files})
            stage = "decode_schema"
            layout, metrics = decoder.schema(hex(guid), size)
            schemas.append({"guid": hex(guid), "size": size, "fields": len(layout.fields), "metrics": len(metrics)})
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append({"guid": hex(guid), "size": size, "stage": stage, "files": files, "error": str(error)})
    try:
        commit = revision(metadata)
    except OSError:
        commit = None
    return {"metadata": str(metadata), "git_commit": commit, "schemas": schemas, "errors": errors,
            "mappings": mappings, "mapping_valid": len(mappings) == len(keys),
            "mapping_count": len(mappings), "schema_count": len(schemas),
            "valid": not errors, "scope": "run inventory" if run_dir else "entire registry"}