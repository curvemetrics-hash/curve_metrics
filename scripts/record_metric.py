#!/usr/bin/env python3
"""Write one pipeline metric record: to the metrics bucket in LocalStack locally, or to the shared
database in aws mode (PLATFORM_MODE=aws).

Usage: record_metric.py <name> <requested_epoch> <ready_epoch> <manual_steps> <outcome>
"""
import json
import os
import sys
import urllib.request

ENDPOINT = "http://localhost:4566"
BUCKET = "curve-metrics-pipeline-metrics"


def main():
    name, requested, ready, manual_steps, outcome = sys.argv[1:6]
    record = {
        "environment": name,
        "requested_epoch": int(requested),
        "ready_epoch": int(ready),
        "elapsed_seconds": int(ready) - int(requested),
        "manual_steps": int(manual_steps),
        "outcome": outcome,
    }
    key = f"{name}-{ready}.json"
    if os.environ.get("PLATFORM_MODE") == "aws":
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from spaces import store
        store.put("metric", key, record)
        print(f"metric recorded in the shared database: {key}  {record}")
        return
    req = urllib.request.Request(
        f"{ENDPOINT}/{BUCKET}/{key}",
        data=json.dumps(record).encode(),
        method="PUT",
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req).read()
    print(f"metric recorded: s3://{BUCKET}/{key}  {record}")


if __name__ == "__main__":
    main()
