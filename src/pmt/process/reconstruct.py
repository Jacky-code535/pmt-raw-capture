"""Explicit time, counter and statistical semantics for offline PMT series."""

import datetime as dt
import math
import statistics
from pmt.process.statistics import summarize
from pmt.process.timeline import timestamp_seconds, load_events, align_events, failure_windows



TOPOLOGY = ("system", "socket", "die", "module")
IDENTITY = ("endpoint", "aggregator", "guid", "metric", "unit") + TOPOLOGY






class Reconstructor:
    def __init__(self, policies):
        self.policies = policies
        self.previous = {}
        for policy in policies.values():
            if policy.get("kind", "gauge") not in ("gauge", "counter"):
                raise ValueError("metric kind must be gauge or counter")
            if policy.get("kind") == "counter":
                bits = policy.get("bits")
                if not isinstance(bits, int) or isinstance(bits, bool) or not 1 <= bits <= 64:
                    raise ValueError("counter bits must be in 1..64")
            gap = policy.get("max_gap_seconds")
            if gap is not None and (not math.isfinite(gap) or gap <= 0):
                raise ValueError("max_gap_seconds must be finite and positive")

    def add(self, row):
        policy = self.policies.get(row["metric"], {})
        key = tuple(row.get(name, "") for name in IDENTITY)
        moment = timestamp_seconds(row["timestamp"])
        value = row["value"]
        result = dict(row, measure="value", validity="valid")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            result.update(value=None, validity="non_numeric")
        elif row.get("known_invalid", False) or value in policy.get("invalid_values", []):
            result.update(value=None, validity="invalid_marker")
        if policy.get("kind", "gauge") == "gauge":
            return [result]
        bits = policy["bits"]
        if result["validity"] == "valid" and (not isinstance(value, int) or not 0 <= value < 2 ** bits):
            result.update(value=None, validity="counter_out_of_range")
        previous = self.previous.pop(key, None)
        validity = result["validity"]
        delta = elapsed = None
        if validity == "valid":
            self.previous[key] = (moment, row["sequence"], value)
            validity = "first_sample"
            if previous:
                elapsed = moment - previous[0]
                if elapsed <= 0:
                    validity = "non_increasing_time"
                elif row["sequence"] != previous[1] + 1:
                    validity = "missing_sample"
                elif elapsed > policy.get("max_gap_seconds", float("inf")):
                    validity = "time_gap"
                elif value < previous[2] and not policy.get("allow_wrap", False):
                    validity = "reset_or_wrap"
                else:
                    delta = (value - previous[2]) % (2 ** bits)
                    validity = "wrap_assumed" if value < previous[2] else "valid"
        return [result, dict(row, value=delta, measure="delta", validity=validity),
                dict(row, value=delta / elapsed if delta is not None else None,
                     measure="rate", unit=row["unit"] + "/s", validity=validity)]
