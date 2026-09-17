"""JSON capture settings expanded into ordinary CLI options."""

import json
from pathlib import Path


def arguments(path):
    settings = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise ValueError("capture config must be a JSON object")
    strings = {"endpoint", "run_id", "experiment", "workload", "note", "platform", "xml_version"}
    paths = {"sysfs_root", "output_root", "metadata"}
    integers = {"samples", "expected_aggregators", "cpu"}
    numbers = {"interval_seconds"}
    flags = {"background", "align_minute"}
    result = []
    for name, value in settings.items():
        option = "--" + name.replace("_", "-")
        if name in flags and type(value) is bool:
            if value:
                result.append(option)
            continue
        valid = ((name in strings | paths and isinstance(value, str)) or
                 (name in integers and type(value) is int) or
                 (name in numbers and type(value) in (int, float)))
        if not valid:
            raise ValueError("unknown capture setting or invalid type: " + name)
        if name in paths:
            value = str((path.resolve().parent / value).resolve())
        result.extend((option, str(value)))
    return result