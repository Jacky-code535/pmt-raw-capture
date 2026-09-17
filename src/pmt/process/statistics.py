import datetime as dt
import math
import statistics



def summarize(values):
    valid = sorted(float(value) for value in values if value is not None and math.isfinite(value))
    if not valid:
        result = dict.fromkeys(("mean", "min", "max", "p95", "std", "cv"))
        result["valid_count"] = 0
        return result
    mean = statistics.mean(valid)
    deviation = statistics.pstdev(valid)
    position = (len(valid) - 1) * 0.95
    lower = math.floor(position)
    upper = math.ceil(position)
    return {
        "mean": mean, "min": valid[0], "max": valid[-1],
        "p95": valid[lower] + (valid[upper] - valid[lower]) * (position - lower),
        "std": deviation, "cv": deviation / abs(mean) if mean else None,
        "valid_count": len(valid),
    }
