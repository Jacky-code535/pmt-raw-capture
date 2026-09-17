from __future__ import annotations
import argparse
import base64
import contextlib
import datetime as dt
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import tempfile
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple



def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as source:
        result = json.load(source)
    if not isinstance(result, dict):
        raise RuntimeError(f"expected JSON object in {path}")
    return result


def read_manifest(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.is_file():
        return records
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"invalid manifest line {line_number}: {error}"
                ) from error
            records.append(record)
    return records


def read_bundle(path: Path) -> Dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as source:
        result = json.load(source)
    if not isinstance(result, dict):
        raise RuntimeError(f"bundle is not a JSON object: {path}")
    return result
