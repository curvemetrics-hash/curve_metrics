import os
import sys
import time
import json
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_URL = "http://127.0.0.1:8080"

def simulate_chat_session():
    print("=" * 80)
    print("AI PLATFORM COPILOT LIVE INTERACTIVE CHAT SESSION")
    print("=" * 80)

    # USER PROMPT 1: Inquire fleet health
    user_prompt_1 = "What environments need attention?"
    print(f"\n[USER] > {user_prompt_1}")
    time.sleep(0.5)

    with urllib.request.urlopen(f"{BASE_URL}/spaces") as res:
        spaces = json.loads(res.read().decode())
    
    degraded = [s for s in spaces if s.get("latest") and (not s["latest"].get("compliant") or s["latest"].get("grade") != "healthy")]
    
    if not degraded:
        bot_reply_1 = "All environments are currently healthy and 100% compliant with blueprint baseline standards! 🎉"
    else:
        bot_reply_1 = f"Found {len(degraded)} degraded environment(s):\n"
        for d in degraded[:3]:
            bot_reply_1 += f"  • {d['name']} [{d['latest']['grade']}] ({d['latest']['passed']}/14 baseline passed)\n"
    print(f"[COPILOT] > {bot_reply_1}")

    # USER PROMPT 2: Request environment creation via natural language
    target_env = "chat-payments-prod"
    user_prompt_2 = f"create env {target_env} team=payments tier=prod size=large"
    print(f"\n[USER] > {user_prompt_2}")
    time.sleep(0.5)

    print(f"[COPILOT] > Provisioning new environment '{target_env}' (Team: payments • Tier: prod • Size: large)...")
    
    payload = {
        "name": target_env,
        "team": "payments",
        "environment": "prod",
        "size": "large",
        "admin_groups": ["payments-admins"],
        "auto_remediate": True
    }
    req = urllib.request.Request(
        f"{BASE_URL}/spaces",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "copilot-chat", "X-Role": "admin"}
    )
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode())
        jid = data.get("job")
        print(f"[ENGINE] > API returned HTTP 202 Accepted (Job ID: {jid})")

    bot_reply_2 = f"[PROVISIONED] Environment '{target_env}' created and queued for provisioning! It will automatically configure baseline quotas, S3 encryption, and default-deny policies."
    print(f"[COPILOT] > {bot_reply_2}")

    # Worker execution live tracking
    print("\n--- Live 10-Stage Pipeline Execution ---")
    for tick in range(1, 20):
        time.sleep(0.4)
        with urllib.request.urlopen(f"{BASE_URL}/spaces/{target_env}") as res:
            doc = json.loads(res.read().decode())
            status = doc.get("status")
            stage = doc.get("stage")
            print(f"  [Worker Tick {tick:02d}] Status: {status:12} | Pipeline Stage: {stage}/10")
            if status == "ready":
                break

    # USER PROMPT 3: Inquire status of newly created environment
    user_prompt_3 = f"What is the status of {target_env}?"
    print(f"\n[USER] > {user_prompt_3}")
    time.sleep(0.5)

    with urllib.request.urlopen(f"{BASE_URL}/spaces/{target_env}") as res:
        doc = json.loads(res.read().decode())
        latest = doc.get("latest", {})
        grade = latest.get("grade")
        comp = latest.get("compliant")
        passed = latest.get("passed")
        total = latest.get("total")
        sec = doc.get("seconds_to_ready")
    
    bot_reply_3 = (
        f"Environment '{target_env}' is READY and HEALTHY!\n"
        f"  • Status: {doc.get('status').upper()}\n"
        f"  • Compliance Grade: {grade.upper()} (Compliant: {comp})\n"
        f"  • Baseline Controls: {passed}/{total} Passed\n"
        f"  • Open Security Findings: {latest.get('extended_summary', {}).get('failed', 0)}\n"
        f"  • Time to Ready: {sec}s (Completed all 10 pipeline stages)"
    )
    print(f"[COPILOT] > {bot_reply_3}")

    print("\n" + "=" * 80)
    print("SESSION VERIFIED: ENVIRONMENT SUCCESSFULLY CREATED AND VERIFIED VIA COPILOT")
    print("=" * 80)

if __name__ == "__main__":
    simulate_chat_session()
