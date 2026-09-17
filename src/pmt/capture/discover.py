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

from pmt.capture.reader import read_text
PMT_ENTRY = re.compile(r"^telem([0-9]+)$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def normalize_guid(raw: str) -> str:
    value = int(raw, 0)
    if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"GUID is outside uint64 range: {raw!r}")
    return f"0x{value:08x}"


def telemetry_sort_key(path: Path) -> int:
    match = PMT_ENTRY.fullmatch(path.name)
    if match is None:
        raise ValueError(f"invalid telemetry entry: {path}")
    return int(match.group(1))


def validate_identifier(value: str, label: str) -> str:
    if value in (".", "..") or not SAFE_ID.fullmatch(value):
        raise ValueError(
            f"{label} must contain only letters, numbers, '.', '_' or '-'"
        )
    return value


def discover_inventory(sysfs_root: Path) -> List[Dict[str, Any]]:
    if not sysfs_root.is_dir():
        raise RuntimeError(f"PMT sysfs directory is unavailable: {sysfs_root}")
    entries = sorted(
        (
            entry
            for entry in sysfs_root.iterdir()
            if entry.is_dir() and PMT_ENTRY.fullmatch(entry.name)
        ),
        key=telemetry_sort_key,
    )
    if not entries:
        raise RuntimeError(f"no telem* entries found under {sysfs_root}")

    inventory: List[Dict[str, Any]] = []
    for entry in entries:
        guid = normalize_guid(read_text(entry / "guid"))
        size = int(read_text(entry / "size"), 0)
        if size <= 0:
            raise RuntimeError(f"{entry.name} reports invalid size {size}")
        if not (entry / "telem").is_file():
            raise RuntimeError(f"{entry.name} has no readable telem file")
        inventory.append(
            {
                "AccessId": entry.name,
                "Guid": guid,
                "Size": size,
                "Path": str(entry / "telem"),
            }
        )
    return inventory


def inventory_identity(
    inventory: Iterable[Dict[str, Any]]
) -> List[Tuple[str, str, int]]:
    return [
        (str(item["AccessId"]), str(item["Guid"]), int(item["Size"]))
        for item in inventory
    ]
