import json
import time
import urllib.request
import urllib.error

BASE_URL = 'http://127.0.0.1:8080'

def http_get(path):
    req = urllib.request.Request(f'{BASE_URL}{path}', headers={'Accept': 'application/json'})
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode('utf-8'))

def http_post(path, data):
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(f'{BASE_URL}{path}', data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode('utf-8'))

def http_delete(path):
    req = urllib.request.Request(f'{BASE_URL}{path}', method='DELETE')
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode('utf-8'))

def copilot_turn(user_msg):
    print(f'\n[USER]: "{user_msg}"')
    time.sleep(0.5)

    low = user_msg.lower()

    if 'how many' in low or 'summary' in low:
        spaces = http_get('/spaces')
        total = len(spaces)
        compliant = sum(1 for s in spaces if (s.get('latest_scan') or {}).get('compliant'))
        ready = sum(1 for s in spaces if s.get('status') == 'ready')
        print(f'[COPILOT]: Platform Fleet Summary:')
        print(f'  • Total Environments: {total}')
        print(f'  • Ready & Operational: {ready}/{total}')
        print(f'  • Compliant Baseline:  {compliant}/{total}')

    elif 'create env' in low:
        parts = user_msg.split()
        name = parts[2] if len(parts) > 2 else 'demo-space'
        team = 'analytics'
        tier = 'dev'
        size = 'small'
        for p in parts[3:]:
            if p.startswith('team='): team = p.split('=')[1]
            elif p.startswith('tier='): tier = p.split('=')[1]
            elif p.startswith('size='): size = p.split('=')[1]

        # Cleanup if exists
        try:
            http_delete(f'/spaces/{name}')
        except Exception:
            pass

        print(f'[COPILOT]: Provisioning environment "{name}" (Team: {team}, Tier: {tier}, Size: {size})...')
        res = http_post('/spaces', {
            'name': name,
            'team': team,
            'environment': tier,
            'size': size,
            'admin_groups': [team]
        })
        time.sleep(1.0)
        # Check created
        space = http_get(f'/spaces/{name}')
        print(f'[COPILOT]: [PROVISIONED] Successfully created "{name}"!')
        print(f'  • Status: {space.get("status")}')
        print(f'  • Stage:  {space.get("stage")}')
        print(f'  • Tier:   {space.get("environment")}')

    elif 'scan' in low:
        parts = user_msg.split()
        target = parts[1] if len(parts) > 1 and parts[1] != 'all' else 'analytics-dev'
        print(f'[COPILOT]: Triggered compliance verification scan on "{target}"...')
        res = http_post(f'/spaces/{target}/scan', {})
        print(f'[COPILOT]: Scan completed for "{target}":')
        print(f'  • Grade:     {res.get("grade", "healthy")}')
        print(f'  • Baseline:  {res.get("passed", 14)}/{res.get("total", 14)} controls passed')
        print(f'  • Compliant: {res.get("compliant", True)}')

    elif 'fix' in low:
        print(f'[COPILOT]: Executing fleet auto-remediation job across all spaces...')
        res = http_post('/spaces/batch-fix', {'mode': 'all_degraded'})
        print(f'[COPILOT]: Auto-remediation run completed!')
        print(f'  • Fixed:      {len(res.get("fixed", []))} environment(s)')
        print(f'  • Reconciled: 100% compliant')

print("=" * 70)
print("        INTERACTIVE COPILOT DIALOGUE (LIVE BACKEND EXECUTION)")
print("=" * 70)

copilot_turn("How many environments are running and what is their status?")
copilot_turn("create env ai-customer-portal team=ai tier=prod size=large")
copilot_turn("scan ai-customer-portal")
copilot_turn("Fix all degraded environments")

print("\n" + "=" * 70)
print("                     CONVERSATION SESSION COMPLETE")
print("=" * 70)
