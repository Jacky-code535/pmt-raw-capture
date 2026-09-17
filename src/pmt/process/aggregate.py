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
        self.connection.execute("CREATE TABLE samples (identity TEXT, value REAL)")

    def add(self, row, fields=GROUP):
        key = json.dumps([row.get(name, "") for name in fields], separators=(",", ":"))
        self.connection.execute("INSERT INTO samples VALUES (?, ?)", (key, float(row["value"]) if row["value"] is not None else None))

    def rows(self, fields=GROUP):
        self.connection.execute("CREATE INDEX IF NOT EXISTS by_identity ON samples(identity, value)")
        self.connection.commit()
        for key, in self.connection.execute("SELECT DISTINCT identity FROM samples ORDER BY identity"):
            values = (entry[0] for entry in self.connection.execute("SELECT value FROM samples WHERE identity=?", (key,)))
            result = dict(zip(fields, json.loads(key)))
            result.update(analysis.summarize(values))
            yield result

    def close(self):
        self.connection.close()
