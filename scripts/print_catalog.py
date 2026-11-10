from spaces import controls, checks

print("=== BASELINE CONTROLS (14) ===")
for cid, area, title, _ in controls.CONTROLS:
    print(f"{cid:8} | {area:12} | {title}")

print("\n=== EXTENDED CHECKS (42) ===")
for c in checks.CHECKS:
    print(f"{c['id']:8} | {c['severity']:6} | {c['area']:14} | {c['title']:35} | Fix: {c.get('fix', '')}")
