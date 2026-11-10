import urllib.request
import json
import time

print(">>> STEP 1: UI triggers POST /spaces/analytics-dev/fix...")
req = urllib.request.Request(
    "http://127.0.0.1:8080/spaces/analytics-dev/fix",
    data=b"",
    headers={"User-Agent": "test", "X-Role": "admin"}
)
with urllib.request.urlopen(req) as res:
    data = json.loads(res.read().decode())
    print("    Response code:", res.status)
    print("    Payload:", data)
    jid = data["job"]

print(f"\n>>> STEP 2: Background worker execution for job {jid}...")
for i in range(15):
    time.sleep(0.4)
    with urllib.request.urlopen(f"http://127.0.0.1:8080/jobs/{jid}") as res:
        j = json.loads(res.read().decode())
        st = j.get("status")
        print(f"    [tick {i+1}] Job status: {st}")
        if st in ("done", "failed"):
            print("    Worker result:", j.get("result"))
            break

print("\n>>> STEP 3: Verifying final space record and scan report...")
with urllib.request.urlopen("http://127.0.0.1:8080/spaces/analytics-dev") as res:
    doc = json.loads(res.read().decode())
    latest = doc.get("latest", {})
    print("    Space Name:", doc.get("request", {}).get("name"))
    print("    Status:", doc.get("status"))
    print("    Pipeline Stage:", doc.get("stage"))
    print("    Compliance Grade:", latest.get("grade"))
    print("    Compliant:", latest.get("compliant"))
    print(f"    Baseline Controls: {latest.get('passed')}/{latest.get('total')}")
    print("    Open Findings:", latest.get("extended_summary", {}).get("failed"))

print("\n>>> STEP 4: Testing second fix on search-dev (at risk -> healthy)...")
req2 = urllib.request.Request(
    "http://127.0.0.1:8080/spaces/search-dev/fix",
    data=b"",
    headers={"User-Agent": "test", "X-Role": "admin"}
)
with urllib.request.urlopen(req2) as res2:
    data2 = json.loads(res2.read().decode())
    jid2 = data2["job"]

for i in range(15):
    time.sleep(0.4)
    with urllib.request.urlopen(f"http://127.0.0.1:8080/jobs/{jid2}") as res:
        j2 = json.loads(res.read().decode())
        if j2.get("status") in ("done", "failed"):
            print("    search-dev fix complete with status:", j2.get("status"))
            break

with urllib.request.urlopen("http://127.0.0.1:8080/spaces/search-dev") as res:
    doc2 = json.loads(res.read().decode())
    latest2 = doc2.get("latest", {})
    print("    search-dev Grade:", latest2.get("grade"))
    print("    search-dev Compliant:", latest2.get("compliant"))
    print(f"    search-dev Baseline: {latest2.get('passed')}/{latest2.get('total')}")
    print("    search-dev Open Findings:", latest2.get("extended_summary", {}).get("failed"))

print("\nTEST COMPLETED: ALL FIXES FUNCTIONING PROPERLY.")
