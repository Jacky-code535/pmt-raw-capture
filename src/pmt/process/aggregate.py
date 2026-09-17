import base64
import contextlib
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import pmt_analysis as analysis
import pmt_bulk_capture as capture

GROUP = analysis.IDENTITY + ("measure",)


class SummaryStore:
    def __init__(self, path):
        self.connection = sqlite3.connect(str(path))
        self.connection.execute(
            "CREATE TABLE samples (identity TEXT, value REAL, valid INTEGER, timestamp TEXT)"
        )

    def add(self, row, fields=GROUP):
        key = json.dumps([row.get(name, "") for name in fields], separators=(",", ":"))
        value = row.get("value")
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        self.connection.execute(
            "INSERT INTO samples VALUES (?, ?, ?, ?)",
            (key, float(value) if valid else None, int(valid), row.get("timestamp", "")),
        )

    def rows(self, fields=GROUP):
        self.connection.execute("CREATE INDEX IF NOT EXISTS by_identity ON samples(identity, value)")
        self.connection.commit()
        for key, in self.connection.execute("SELECT DISTINCT identity FROM samples ORDER BY identity"):
            values = (entry[0] for entry in self.connection.execute("SELECT value FROM samples WHERE identity=?", (key,)))
            result = dict(zip(fields, json.loads(key)))
            result.update(analysis.summarize(values))
            yield result

    def quality_rows(self, expected_count, fields=GROUP):
        self.connection.commit()
        query = (
            "SELECT identity, COUNT(*), SUM(valid), MIN(timestamp), MAX(timestamp) "
            "FROM samples GROUP BY identity ORDER BY identity"
        )
        for key, observed, valid, first_timestamp, last_timestamp in self.connection.execute(query):
            result = dict(zip(fields, json.loads(key)))
            result.update({
                "expected_count": expected_count,
                "observed_count": observed,
                "valid_count": valid,
                "invalid_count": observed - valid,
                "missing_count": max(expected_count - observed, 0),
                "valid_rate": valid / expected_count if expected_count else None,
                "first_timestamp": first_timestamp,
                "last_timestamp": last_timestamp,
            })
            yield result

    def close(self):
        self.connection.close()
