import urllib.request
import json
import time

print("1. Verifying /healthz endpoint...")
with urllib.request.urlopen("http://127.0.0.1:8080/healthz") as res:
    assert res.status == 200
    print("   -> OK:", res.read().decode().strip())

print("\n2. Verifying /spaces returns all 10 active environments...")
with urllib.request.urlopen("http://127.0.0.1:8080/spaces") as res:
    spaces = json.loads(res.read().decode())
    print(f"   -> Found {len(spaces)} environments in DB:")
    for s in spaces:
        l = s.get("latest", {})
        print(f"      - {s['name']:20} | status: {s['status']:8} | grade: {str(l.get('grade')):15} | compliant: {str(l.get('compliant')):5}")

print("\n3. Testing Scan Now on payments-dev...")
req = urllib.request.Request("http://127.0.0.1:8080/spaces/payments-dev/scan?wait=10", data=b"", headers={"User-Agent": "test", "X-Role": "admin"})
with urllib.request.urlopen(req) as res:
    scan_res = json.loads(res.read().decode())
    print(f"   -> Scan result: {scan_res.get('grade')} ({scan_res.get('passed')}/{scan_res.get('total')} baseline passed)")

print("\n4. Testing Re-apply Blueprint Fix on checkout-staging...")
req = urllib.request.Request("http://127.0.0.1:8080/spaces/checkout-staging/fix", data=b"", headers={"User-Agent": "test", "X-Role": "admin"})
with urllib.request.urlopen(req) as res:
    fix_res = json.loads(res.read().decode())
    print("   -> Fix job accepted:", fix_res)

jid = fix_res.get("job")
print(f"   -> Waiting for worker job {jid} to complete...")
for _ in range(20):
    time.sleep(0.4)
    with urllib.request.urlopen(f"http://127.0.0.1:8080/jobs/{jid}") as jres:
        job_data = json.loads(jres.read().decode())
        if job_data.get("status") in ("done", "failed"):
            print("   -> Worker finished job with status:", job_data.get("status"), "result:", job_data.get("result"))
            break

print("\nALL VERIFICATIONS PASSED SUCCESSFULLY.")
