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



def topology_map(path):
    if path is None:
        return {}
    result = {}
    with path.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            key = (row["endpoint"], row["aggregator"], row.get("metric", ""))
            if key in result:
                raise ValueError("duplicate topology key: " + repr(key))
            result[key] = {name: row.get(name, "") for name in analysis.TOPOLOGY}
    return result


def decoded_rows(document, results, topology):
    items = document["TelemetryData"]
    if [record["index"] for record in results] != list(range(len(items))):
        raise ValueError("decoder returned missing or reordered aggregator records")
    for item, record in zip(items, results):
        result = record["result"]
        if not result["exact_guid_size_match"] or result["reported_size_bytes"] != item["Size"]:
            raise ValueError("decoder did not confirm exact GUID+Size")
        if capture.normalize_guid(result["guid"]) != capture.normalize_guid(item["Guid"]):
            raise ValueError("decoder GUID differs from raw record")
        endpoint = document["Capture"]["Endpoint"]
        access = item["attributes"]["AccessId"]
        names = set()
        for metric in result["metrics"]:
            if metric["name"] in names:
                raise ValueError("decoder returned duplicate metric name")
            names.add(metric["name"])
            row = {"timestamp": item["attributes"]["CapturedAt"], "endpoint": endpoint,
                   "metric": metric["name"], "value": metric["value"], "unit": metric.get("unit", ""),
                     "known_invalid": metric.get("known_invalid", False),
                   "sequence": document["Capture"]["Sequence"], "aggregator": access,
                   "guid": capture.normalize_guid(item["Guid"])}
            labels = topology.get((endpoint, access, metric["name"]), topology.get((endpoint, access, ""), {}))
            row.update({name: labels.get(name, endpoint if name == "system" else "") for name in analysis.TOPOLOGY})
            yield row
