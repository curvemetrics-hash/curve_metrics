import sqlite3
import json

conn = sqlite3.connect(".local/platform.db")
cur = conn.cursor()
cur.execute("SELECT k, doc FROM kv WHERE ns='space'")
rows = cur.fetchall()
print(f"Total spaces: {len(rows)}")
for k, doc_str in rows:
    data = json.loads(doc_str)
    latest = data.get("latest", {})
    grade = latest.get("grade")
    compliant = latest.get("compliant")
    ctrls = latest.get("controls", [])
    failed_ctrls = [(c["id"], c.get("evidence")) for c in ctrls if not c.get("passed")]
    findings = [(f["id"], f["severity"], f["title"], f.get("fix")) for f in latest.get("findings", [])]
    print(f"\n[{k}] Grade: {grade} | Compliant: {compliant}")
    if failed_ctrls:
        print("  Failed Baseline Controls:")
        for cid, evid in failed_ctrls:
            print(f"    - {cid}: {evid}")
    if findings:
        print("  Extended Findings:")
        for fid, sev, title, fix in findings:
            print(f"    - [{sev.upper()}] {fid}: {title} -> Remediation: {fix}")
conn.close()
