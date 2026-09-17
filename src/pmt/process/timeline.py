import datetime as dt
import math


def timestamp_seconds(text):
    parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a UTC offset")
    return parsed.timestamp()


def load_events(rows, offset_seconds=0):
    if not math.isfinite(offset_seconds):
        raise ValueError("event offset must be finite")
    events = []
    for row in rows:
        start = timestamp_seconds(row["start"]) + offset_seconds
        end = timestamp_seconds(row["end"]) + offset_seconds
        if end <= start:
            raise ValueError("event end must be after start")
        failure = row.get("failure_time", "")
        events.append(dict(row, start_seconds=start, end_seconds=end,
                           failure_seconds=timestamp_seconds(failure) + offset_seconds if failure else None))
    return events


def align_events(row, events):
    moment = timestamp_seconds(row["timestamp"])
    matches = [event for event in events if event["start_seconds"] <= moment < event["end_seconds"]]
    return [dict(row, phase=event["phase"], test_item=event["test_item"],
                 status=event.get("status", "")) for event in matches]


def failure_windows(row, events, before, after):
    moment = timestamp_seconds(row["timestamp"])
    return [dict(row, phase=event["phase"], test_item=event["test_item"],
                 failure_time=event["failure_time"], relative_seconds=moment - event["failure_seconds"])
            for event in events if event["failure_seconds"] is not None
            and -before <= moment - event["failure_seconds"] <= after]