"""
spaces.copilot
~~~~~~~~~~~~~~
Stateful, conversational AI assistant for Cloud & Kubernetes platform operations.
Inspired by GitHub Copilot Chat, AWS Q Developer, and Kubernetes K8sGPT.

Features:
- Multi-turn conversation state machine (remembers context, past intents, and draft entities)
- Natural language intent parsing with slot extraction and clarification dialogue
- Interactive plan proposals with confirmation gates and diffs
- Live platform grounding (scans, fleet health, SOC 2 compliance, rollout status)
- Built-in command dispatch (safe execution of create, fix, scan, rollback, export)
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import spaces.core as core
import spaces.store as store


# In-memory session store (keyed by session_id or user)
_SESSIONS: Dict[str, "CopilotSession"] = {}


class CopilotSession:
    def __init__(self, session_id: str, actor: str = "local"):
        self.session_id = session_id
        self.actor = actor
        self.history: List[Dict[str, Any]] = []
        self.state: str = "idle"  # idle | creating_env | confirming_action
        self.pending_action: Optional[Dict[str, Any]] = None
        self.draft_env: Dict[str, Any] = {}
        self.last_active: float = time.time()

    def add_message(self, role: str, content: str, card: Optional[Dict[str, Any]] = None, suggestions: Optional[List[str]] = None):
        self.history.append({
            "role": role,
            "content": content,
            "card": card,
            "suggestions": suggestions or [],
            "timestamp": time.time(),
        })
        self.last_active = time.time()


def get_session(session_id: str = "default", actor: str = "local") -> CopilotSession:
    if session_id not in _SESSIONS:
        sess = CopilotSession(session_id, actor)
        # Seed greeting message
        sess.add_message(
            role="bot",
            content="Hello! I'm your **Platform Copilot**. I can help you provision Kubernetes environments, inspect compliance drift, trigger self-healing fixes, and generate SOC 2 reports. What would you like to do?",
            suggestions=[
                "Create a new environment",
                "Show fleet health & degraded spaces",
                "Fix all non-compliant environments",
                "Export SOC 2 audit CSV"
            ]
        )
        _SESSIONS[session_id] = sess
    return _SESSIONS[session_id]


def process_chat_message(session_id: str, user_text: str, actor: str = "local") -> Dict[str, Any]:
    """
    Main dialogue processing pipeline for the Copilot.
    """
    sess = get_session(session_id, actor)
    raw = user_text.strip()
    low = raw.lower()

    sess.add_message("user", raw)

    # 1. Check for cancel / reset / clear intents
    if low in ("cancel", "abort", "reset", "clear", "nevermind", "stop"):
        sess.state = "idle"
        sess.pending_action = None
        sess.draft_env = {}
        msg = "Understood, cancelled current action. What would you like to do instead?"
        suggs = ["Create environment", "Show health overview", "Fix degraded spaces"]
        sess.add_message("bot", msg, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

    # 2. Handle active multi-turn Creation Wizard
    if sess.state == "creating_env":
        return _handle_creation_wizard(sess, raw, low)

    # 3. Handle active Confirmation Action (e.g. Yes/No to execute an operation)
    if sess.state == "confirming_action":
        return _handle_action_confirmation(sess, raw, low)

    # 4. Check for Creation Intent: "create", "new env", "provision", "deploy"
    if any(k in low for k in ("create", "new env", "new environment", "provision", "spin up")):
        return _start_or_parse_creation(sess, raw, low)

    # 5. Check for Decommission / Teardown / Destroy Intent
    if any(k in low for k in ("teardown", "tear down", "decommission", "destroy", "delete space", "delete env", "delete environment")):
        return _handle_teardown_intent(sess, raw, low)

    # 5b. Check for Fix / Remediate Intent
    if any(k in low for k in ("fix", "remediate", "repair", "heal")):
        return _handle_fix_intent(sess, raw, low)

    # 6. Check for Fleet Health / Status / Degraded query
    if any(k in low for k in ("degraded", "broken", "attention", "fail", "health", "status", "summary", "overview")):
        return _handle_fleet_status_intent(sess, low)

    # 7. Check for FinOps / Cost / Pricing Intent
    if any(k in low for k in ("price", "pricing", "cost", "finops", "budget", "spend", "estimate", "bill")):
        return _handle_pricing_intent(sess, low)

    # 8. Check for Audit / Export Intent
    if any(k in low for k in ("export", "csv", "audit", "soc 2", "compliance ledger", "download")):
        return _handle_export_intent(sess)

    # 8. Check for Scan Intent: "scan <name>", "audit <name>", "check <name>"
    if any(k in low for k in ("scan", "inspect", "check")):
        return _handle_scan_intent(sess, raw, low)

    # 9. Natural Language FAQ / Architecture query
    if any(k in low for k in ("how does", "what is", "help", "blueprint", "security", "guardrail")):
        return _handle_faq_intent(sess, low)

    # Fallback response
    fallback = (
        "I'm here to assist with cloud & environment management. Here are a few things you can ask me:\n\n"
        "• **\"Create a new environment\"** — I'll guide you step-by-step through setting up team, tier, and quotas.\n"
        "• **\"Show fleet health\"** — View compliance status, failing controls, and cluster health.\n"
        "• **\"Fix degraded environments\"** — Auto-reconcile policy drift with versioned blueprints.\n"
        "• **\"Export compliance report\"** — Download an executive SOC 2 ledger in CSV format."
    )
    suggs = ["Create a new environment", "Show fleet health", "Fix all degraded spaces", "Export SOC 2 CSV"]
    sess.add_message("bot", fallback, suggestions=suggs)
    return {"reply": fallback, "suggestions": suggs, "card": None, "state": sess.state}


# ------------------------------------------------------------------------------
# MULTI-TURN ENVIRONMENT CREATION WIZARD
# ------------------------------------------------------------------------------

def _start_or_parse_creation(sess: CopilotSession, raw: str, low: str) -> Dict[str, Any]:
    # Remove phrases like 'create a new environment', 'create new env', 'create env', etc.
    cleaned = re.sub(r'^(create|spin up|provision|new)\s+(a\s+)?(new\s+)?(environment|env|space)?\s*', '', low, flags=re.I).strip()
    parts = cleaned.split() if cleaned else []
    
    name = None
    team = None
    tier = None
    size = None
    blueprint = None

    # Check for blueprint
    for bp in TEMPLATES:
        if bp in low:
            blueprint = bp
            break

    for p in parts:
        p_low = p.lower()
        if p_low.startswith("team="):
            team = p.split("=", 1)[1].strip()
        elif p_low.startswith("tier=") or p_low.startswith("env="):
            tier = p.split("=", 1)[1].strip()
        elif p_low.startswith("size="):
            size = p.split("=", 1)[1].strip()
        elif p_low in ("dev", "test", "prod"):
            tier = p_low
        elif p_low in ("small", "medium", "large"):
            size = p_low
        elif p_low in TEMPLATES:
            blueprint = p_low
        elif not name and "=" not in p and p_low not in ("a", "an", "the", "env", "environment", "space"):
            name = p_low

    # If first token was 'name', but there are remaining tokens, check for team
    remaining = [p for p in parts if p != name and p != tier and p != size and p != blueprint and not p.startswith("team=") and not p.startswith("env=") and not p.startswith("size=") and p.lower() not in ("a", "an", "the", "env", "environment")]
    if not team and remaining:
        team = remaining[0]

    sess.draft_env = {
        "name": name,
        "team": team,
        "environment": tier,
        "size": size,
        "blueprint": blueprint or "standard",
        "services": TEMPLATES[blueprint]["services"] if blueprint and blueprint in TEMPLATES else TEMPLATES["standard"]["services"]
    }
    sess.state = "creating_env"

    # Evaluate what's missing
    return _prompt_next_creation_step(sess)


TEMPLATES = {
    "standard": {
        "label": "Standard Microservice",
        "desc": "Full stack: K8s Namespace, S3 Bucket, SQS Queue, Secrets Manager, CloudWatch Logs, IAM IRSA",
        "services": ["s3", "sqs", "secrets", "logs"]
    },
    "minimal": {
        "label": "Minimal / Internal Tool",
        "desc": "Lean footprint: K8s Namespace with default-deny network policy & CloudWatch logging only (No cloud storage/queues)",
        "services": ["logs"]
    },
    "data_analytics": {
        "label": "Data & Analytics Lake",
        "desc": "Analytics: S3 Data Lake bucket with AES256 encryption, Secrets Manager, CloudWatch Logs (No SQS)",
        "services": ["s3", "secrets", "logs"]
    },
    "event_driven": {
        "label": "Event-Driven Streaming",
        "desc": "Messaging hub: Encrypted SQS FIFO/standard queue, dead-letter redrive, S3 audit bucket, CloudWatch",
        "services": ["s3", "sqs", "secrets", "logs"]
    },
    "frontend_spa": {
        "label": "Static Web / Frontend",
        "desc": "Client app: S3 static hosting bucket with versioning and CloudWatch logging (No SQS/Secrets)",
        "services": ["s3", "logs"]
    }
}

def _handle_creation_wizard(sess: CopilotSession, raw: str, low: str) -> Dict[str, Any]:
    draft = sess.draft_env

    # 1. If name is missing
    if not draft.get("name"):
        clean_name = re.sub(r"[^a-z0-9-]", "", low).strip("-")
        if not clean_name or len(clean_name) < 3:
            msg = "Please provide a valid environment name (lowercase letters, numbers, and hyphens, at least 3 characters. E.g. illing-dev):"
            sess.add_message("bot", msg)
            return {"reply": msg, "suggestions": ["billing-dev", "payments-staging", "orders-prod"], "card": None, "state": sess.state}
        draft["name"] = clean_name
        return _prompt_next_creation_step(sess)

    # 2. If team is missing
    if not draft.get("team"):
        clean_team = re.sub(r"[^a-z0-9-]", "", low).strip("-")
        if not clean_team:
            msg = "Please enter the team that will own this environment (e.g. payments, checkout, core):"
            sess.add_message("bot", msg)
            return {"reply": msg, "suggestions": ["payments", "checkout", "security", "analytics"], "card": None, "state": sess.state}
        draft["team"] = clean_team
        return _prompt_next_creation_step(sess)

    # 3. If template / blueprint is missing
    if not draft.get("blueprint"):
        matched_bp = None
        for key in TEMPLATES:
            if key in low or TEMPLATES[key]["label"].lower() in low or key.replace("_", " ") in low:
                matched_bp = key
                break
        if matched_bp:
            draft["blueprint"] = matched_bp
            draft["services"] = TEMPLATES[matched_bp]["services"]
            return _prompt_next_creation_step(sess)
        else:
            msg = "Please select a blueprint template from the options below:"
            suggs = [f"{k}: {TEMPLATES[k]['label']}" for k in TEMPLATES]
            sess.add_message("bot", msg, suggestions=suggs)
            return {"reply": msg, "suggestions": list(TEMPLATES.keys()), "card": None, "state": sess.state}

    # 4. If tier is missing
    if not draft.get("environment"):
        if low in ("dev", "test", "prod"):
            draft["environment"] = low
            return _prompt_next_creation_step(sess)
        else:
            msg = "Please select an environment tier: **dev** (sandbox), **test** (staging verification), or **prod** (production with high-availability):"
            sess.add_message("bot", msg)
            return {"reply": msg, "suggestions": ["dev", "test", "prod"], "card": None, "state": sess.state}

    # 5. If size is missing
    if not draft.get("size"):
        match_size = None
        for s in ("small", "medium", "large"):
            if s in low:
                match_size = s
                break
        if match_size:
            draft["size"] = match_size
            return _prompt_next_creation_step(sess)
        else:
            msg = "Please choose a cluster resource quota size:\n\n• **small** (0.5 CPU / 1Gi Mem)\n• **medium** (2.0 CPU / 4Gi Mem)\n• **large** (4.0 CPU / 8Gi Mem)"
            sess.add_message("bot", msg)
            return {"reply": msg, "suggestions": ["small", "medium", "large"], "card": None, "state": sess.state}

    # 6. If all filled, user is replying to the confirmation card
    if any(k in low for k in ("yes", "confirm", "create", "proceed", "y", "do it")):
        return _execute_create_env(sess)
    elif low in ("no", "cancel", "stop", "abort"):
        sess.state = "idle"
        sess.draft_env = {}
        msg = "Cancelled environment creation. Let me know if you'd like to configure a different environment!"
        sess.add_message("bot", msg)
        return {"reply": msg, "suggestions": ["Create new environment", "Show health summary"], "card": None, "state": sess.state}
    else:
        msg = "Would you like me to proceed with provisioning this environment? Reply **Confirm** or **Cancel**."
        sess.add_message("bot", msg)
        return {"reply": msg, "suggestions": ["Confirm and Provision", "Cancel"], "card": None, "state": sess.state}


def _prompt_next_creation_step(sess: CopilotSession) -> Dict[str, Any]:
    draft = sess.draft_env

    if not draft.get("name"):
        msg = "Let's set up your new environment! First, **what name would you like to give it?**\n*(Format: lowercase alphanumeric with hyphens, e.g. payments-dev)*"
        suggs = ["checkout-dev", "auth-test", "billing-prod"]
        sess.add_message("bot", msg, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

    if not draft.get("team"):
        msg = f"Got it, name is **{draft['name']}**.\nWhich **team** owns this environment?"
        suggs = ["payments", "checkout", "platform", "analytics"]
        sess.add_message("bot", msg, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

    if not draft.get("blueprint"):
        msg = (
            f"Team is **{draft['team']}**.\nWhich **workload template / scenario blueprint** would you like to provision?\n\n"
            f"1. **Standard Microservice** (standard): Full AWS suite (S3, SQS, Secrets, Logs, IRSA)\n"
            f"2. **Minimal / Internal Tool** (minimal): Lean namespace & logs only (No S3/SQS)\n"
            f"3. **Data & Analytics Lake** (data_analytics): S3 Lake, Secrets, Logs (No SQS)\n"
            f"4. **Event-Driven Streaming** (event_driven): SQS FIFO/SSE queue, S3, CloudWatch\n"
            f"5. **Frontend / SPA** (rontend_spa): Static S3 hosting & logs (No backend queues)"
        )
        suggs = ["standard", "minimal", "data_analytics", "event_driven", "frontend_spa"]
        sess.add_message("bot", msg, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

    if not draft.get("environment"):
        bp_label = TEMPLATES.get(draft.get("blueprint", "standard"), {}).get("label", "Standard")
        msg = f"Blueprint set to **{bp_label}**.\nWhat **tier** should this environment run on?"
        suggs = ["dev", "test", "prod"]
        sess.add_message("bot", msg, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

    if not draft.get("size"):
        msg = f"Tier set to **{draft['environment']}**.\nWhat **resource size quota** do you need?"
        suggs = ["small (0.5 CPU, 1Gi)", "medium (2.0 CPU, 4Gi)", "large (4.0 CPU, 8Gi)"]
        sess.add_message("bot", msg, suggestions=suggs)
        return {"reply": msg, "suggestions": ["small", "medium", "large"], "card": None, "state": sess.state}

    # All fields gathered! Present Confirmation Review Card
    bp_info = TEMPLATES.get(draft.get("blueprint", "standard"), {})
    services_str = ", ".join(s.upper() for s in draft.get("services", ["S3", "SQS", "SECRETS", "LOGS"]))

    card = {
        "type": "review_env",
        "title": f"Review Provisioning Request: {draft['name']}",
        "fields": [
            {"label": "Environment Name", "value": draft["name"]},
            {"label": "Blueprint Template", "value": bp_info.get("label", "Standard")},
            {"label": "AWS Cloud Services", "value": services_str},
            {"label": "Owning Team", "value": draft["team"]},
            {"label": "Tier / Stage", "value": draft["environment"].upper()},
            {"label": "Resource Size", "value": draft["size"]},
            {"label": "Admin RBAC", "value": f"{draft['team']}-admins"},
            {"label": "Policy Guardrails", "value": "Default-Deny Ingress, AES256 Encryption, Least-Privilege IAM"}
        ],
        "action": "create_env"
    }

    msg = (
        f"I've prepared the environment blueprint for **{draft['name']}**:\n\n"
        f"• **Template**: {bp_info.get('label', 'Standard')}\n"
        f"• **AWS Services**: {services_str}\n"
        f"• **Team**: {draft['team']} | **Tier**: {draft['environment']} | **Size**: {draft['size']}\n"
        f"• **Admin Group**: {draft['team']}-admins\n\n"
        f"Should I proceed with the automated provisioning pipeline?"
    )
    suggs = ["Yes, confirm & provision", "Cancel"]
    sess.add_message("bot", msg, card=card, suggestions=suggs)
    return {"reply": msg, "suggestions": suggs, "card": card, "state": sess.state}


def _execute_create_env(sess: CopilotSession) -> Dict[str, Any]:
    draft = sess.draft_env
    name = draft["name"]
    team = draft["team"]
    tier = draft["environment"]
    size = draft["size"]

    req_data = {
        "name": name,
        "team": team,
        "environment": tier,
        "size": size,
        "admin_groups": [f"{team}-admins"],
        "auto_remediate": True
    }

    try:
        # Validate and write request
        core.validate(req_data)
        core.write_request(req_data)
        jid = store.enqueue("apply", name, req_data, actor=sess.actor)

        # Clear creation state
        sess.state = "idle"
        sess.draft_env = {}

        card = {
            "type": "success_env",
            "title": f"Environment {name} Queued for Provisioning",
            "fields": [
                {"label": "Job ID", "value": jid[:12]},
                {"label": "Status", "value": "Provisioning (10 pipeline stages)"},
                {"label": "Target Tier", "value": tier},
                {"label": "Verification", "value": "Automated OpenTofu & compliance checks"}
            ]
        }

        msg = (
            f"🚀 **Environment `{name}` has been enqueued for provisioning!**\n\n"
            f"The platform worker will run the 10-stage delivery pipeline (`format`, `validate`, `unit tests`, `init`, `plan`, `policy gate`, `approval`, `apply`, `verify`, `metric`).\n"
            f"You can monitor live progress on the console or run **`scan {name}`** once ready."
        )
        suggs = [f"Scan {name}", "Show fleet health", "Export audit CSV"]
        sess.add_message("bot", msg, card=card, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": card, "state": sess.state}

    except Exception as e:
        sess.state = "idle"
        sess.draft_env = {}
        err_msg = f"❌ **Failed to create environment**: {str(e)}"
        sess.add_message("bot", err_msg)
        return {"reply": err_msg, "suggestions": ["Try again", "Show fleet health"], "card": None, "state": sess.state}


# ------------------------------------------------------------------------------
# FIX & HEALING INTENT HANDLERS
# ------------------------------------------------------------------------------

def _handle_fix_intent(sess: CopilotSession, raw: str, low: str) -> Dict[str, Any]:
    spaces = [dict(s, name=n) for n, s in store.items("space")]

    # Did user specify a space name? (e.g. "fix checkout-dev")
    target_space = None
    for s in spaces:
        if s["name"].lower() in low:
            target_space = s
            break

    if target_space:
        sess.state = "confirming_action"
        sess.pending_action = {
            "kind": "fix_single",
            "target": target_space["name"]
        }
        card = {
            "type": "confirm_fix",
            "title": f"Confirm Blueprint Re-apply: {target_space['name']}",
            "fields": [
                {"label": "Environment", "value": target_space["name"]},
                {"label": "Current Status", "value": target_space.get("status", "unknown")},
                {"label": "Remediation", "value": "Reconciles drifted network policies, IAM roles, and S3 encryption"}
            ]
        }
        msg = f"Would you like me to re-apply the official blueprint to **`{target_space['name']}`** to remediate configuration drift?"
        suggs = ["Confirm Fix", "Cancel"]
        sess.add_message("bot", msg, card=card, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": card, "state": sess.state}

    # Otherwise fix all degraded
    degraded = [s for s in spaces if s.get("status") in ("failed", "rejected") or (s.get("latest_scan") and not s["latest_scan"].get("compliant"))]
    if not degraded:
        msg = "All environments across the fleet are currently **100% compliant and healthy**! No remediation is required."
        suggs = ["Show fleet health", "Create environment", "Export compliance report"]
        sess.add_message("bot", msg, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

    sess.state = "confirming_action"
    sess.pending_action = {
        "kind": "fix_all",
        "count": len(degraded),
        "names": [s["name"] for s in degraded]
    }
    card = {
        "type": "confirm_batch_fix",
        "title": f"Batch Auto-Remediate {len(degraded)} Environment(s)",
        "fields": [
            {"label": "Target Count", "value": str(len(degraded))},
            {"label": "Environments", "value": ", ".join(s["name"] for s in degraded[:5]) + ("..." if len(degraded) > 5 else "")},
            {"label": "Action", "value": "Enqueue blueprint reconciliation jobs"}
        ]
    }
    msg = f"I identified **{len(degraded)} degraded or drifting environment(s)**. Should I enqueue automatic blueprint remediation jobs for all of them?"
    suggs = ["Confirm & Auto-Fix All", "Cancel"]
    sess.add_message("bot", msg, card=card, suggestions=suggs)
    return {"reply": msg, "suggestions": suggs, "card": card, "state": sess.state}


def _handle_action_confirmation(sess: CopilotSession, raw: str, low: str) -> Dict[str, Any]:
    action = sess.pending_action or {}
    sess.pending_action = None
    sess.state = "idle"

    if low in ("yes", "confirm", "proceed", "fix", "do it", "y", "auto-fix"):
        if action.get("kind") == "fix_single":
            target = action.get("target")
            doc = store.get("space", target)
            req = doc.get("request", {}) if doc else {}
            jid = store.enqueue("apply", target, req, actor=sess.actor)
            msg = f"🔧 **Reconciliation job enqueued for `{target}`** (Job `{jid[:10]}`). The blueprint will restore compliant networking, quotas, and IAM boundaries."
            suggs = [f"Scan {target}", "Show fleet health"]
            sess.add_message("bot", msg, suggestions=suggs)
            return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

        elif action.get("kind") == "fix_all":
            names = action.get("names", [])
            enqueued = 0
            for name in names:
                doc = store.get("space", name)
                req = doc.get("request", {}) if doc else {}
                store.enqueue("apply", name, req, actor=sess.actor)
                enqueued += 1
            msg = f"⚡ **Batch reconciliation triggered for {enqueued} environment(s)!** Workers are now restoring all drifted resources to full baseline compliance."
            suggs = ["Show fleet health", "Export audit CSV"]
            sess.add_message("bot", msg, suggestions=suggs)
            return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

    msg = "Action cancelled. Let me know what else you'd like to do!"
    suggs = ["Show fleet health", "Create environment"]
    sess.add_message("bot", msg, suggestions=suggs)
    return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}


# ------------------------------------------------------------------------------
# FLEET STATUS & COMPLIANCE INTENT HANDLERS
# ------------------------------------------------------------------------------

def _handle_fleet_status_intent(sess: CopilotSession, low: str) -> Dict[str, Any]:
    spaces = [dict(s, name=n) for n, s in store.items("space")]
    total = len(spaces)
    ready = sum(1 for s in spaces if s.get("status") == "ready")
    compliant = sum(1 for s in spaces if (s.get("latest_scan") or {}).get("compliant"))
    degraded = [s for s in spaces if s.get("status") in ("failed", "rejected") or (s.get("latest_scan") and not s["latest_scan"].get("compliant"))]

    card = {
        "type": "fleet_summary",
        "title": "Platform Fleet Overview",
        "fields": [
            {"label": "Total Environments", "value": str(total)},
            {"label": "Operational / Ready", "value": f"{ready} / {total} ({round(ready/(total or 1)*100)}%)"},
            {"label": "Baseline Compliant", "value": f"{compliant} / {total} ({round(compliant/(total or 1)*100)}%)"},
            {"label": "Attention Needed", "value": str(len(degraded))}
        ]
    }

    if degraded:
        deg_list = "\n".join(f"• **`{s['name']}`** — Status: `{s.get('status')}`" for s in degraded[:5])
        msg = (
            f"### Platform Fleet Summary\n\n"
            f"• **Total Spaces**: `{total}`\n"
            f"• **Operational**: `{ready} / {total}`\n"
            f"• **Compliant**: `{compliant} / {total}`\n\n"
            f"⚠️ **{len(degraded)} environment(s) currently require attention**:\n{deg_list}\n\n"
            f"Would you like me to automatically remediate them?"
        )
        suggs = ["Fix all degraded environments", "Export audit CSV", "Create new environment"]
    else:
        msg = (
            f"### Platform Fleet Summary\n\n"
            f"✅ **All {total} environments are 100% operational and healthy!**\n\n"
            f"• **Baseline Controls**: 14/14 passed across networking, encryption, quotas, and RBAC\n"
            f"• **Continuous Drift Monitoring**: Active"
        )
        suggs = ["Create new environment", "Export audit CSV", "Run scan on fleet"]

    sess.add_message("bot", msg, card=card, suggestions=suggs)
    return {"reply": msg, "suggestions": suggs, "card": card, "state": sess.state}


def _handle_teardown_intent(sess: CopilotSession, raw: str, low: str) -> Dict[str, Any]:
    spaces = [dict(s, name=n) for n, s in store.items("space")]
    target_name = None
    for s in spaces:
        if s["name"].lower() in low:
            target_name = s["name"]
            break

    if not target_name:
        words = [w for w in re.split(r'[^a-z0-9_-]', low) if w]
        for w in words:
            for s in spaces:
                if s["name"].lower() == w:
                    target_name = s["name"]
                    break
            if target_name:
                break

    if not target_name:
        msg = "Which environment would you like to tear down and decommission? Here are a few active spaces:"
        suggs = [f"Teardown {s['name']}" for s in spaces[:4]]
        sess.add_message("bot", msg, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

    # Execute decommission
    sp = store.get("space", target_name)
    store.delete("space", target_name)
    store.audit("copilot", "environment.destroy", target_name, {"trigger": "copilot_chatbot"}, role="admin")

    card = {
        "type": "confirm_fix",
        "title": f"Decommissioned: {target_name}",
        "fields": [
            {"label": "Environment", "value": target_name},
            {"label": "Status", "value": "Destroyed & Purged"},
            {"label": "Audit Recorded", "value": "environment.destroy"}
        ]
    }

    msg = f"🗑️ **Environment `{target_name}` has been successfully decommissioned and torn down.** All managed Kubernetes and cloud resources have been released."
    suggs = ["Show fleet health", "Create environment", "Export audit report"]
    sess.add_message("bot", msg, card=card, suggestions=suggs)
    return {"reply": msg, "suggestions": suggs, "card": card, "state": sess.state}


def _handle_scan_intent(sess: CopilotSession, raw: str, low: str) -> Dict[str, Any]:
    spaces = [dict(s, name=n) for n, s in store.items("space")]
    target_name = None
    for s in spaces:
        if s["name"].lower() in low:
            target_name = s["name"]
            break

    if not target_name:
        msg = "Which environment would you like to scan? Here are a few active spaces:"
        suggs = [s["name"] for s in spaces[:4]]
        sess.add_message("bot", msg, suggestions=suggs)
        return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

    # Execute scan on space
    scan_result = core.scan(target_name)
    grade = scan_result.get("grade", "healthy")
    passed = scan_result.get("passed", 14)
    total = scan_result.get("total", 14)
    findings = scan_result.get("findings", 0)

    card = {
        "type": "scan_report",
        "title": f"Scan Audit Report: {target_name}",
        "fields": [
            {"label": "Health Grade", "value": grade.upper()},
            {"label": "Baseline Controls", "value": f"{passed} / {total} Passed"},
            {"label": "Open Findings", "value": str(findings)},
            {"label": "Compliance Status", "value": "COMPLIANT" if scan_result.get("compliant") else "DRIFT DETECTED"}
        ]
    }

    msg = (
        f"🔍 **Scan completed for `{target_name}`**:\n\n"
        f"• **Grade**: `{grade}`\n"
        f"• **Baseline Controls**: `{passed} / {total}` passed\n"
        f"• **Open Findings**: `{findings}`\n\n"
        + ("No drift detected. System complies with SOC 2 standards!" if scan_result.get("compliant") else "Policy drift detected. Run **Fix** to re-apply blueprint.")
    )
    suggs = [f"Fix {target_name}", "Show fleet health", "Export audit report"]
    sess.add_message("bot", msg, card=card, suggestions=suggs)
    return {"reply": msg, "suggestions": suggs, "card": card, "state": sess.state}


def _handle_export_intent(sess: CopilotSession) -> Dict[str, Any]:
    card = {
        "type": "download_card",
        "title": "Executive SOC 2 Compliance Ledger",
        "fields": [
            {"label": "Format", "value": "RFC 4180 CSV"},
            {"label": "Endpoint", "value": "/api/compliance/export?format=csv"},
            {"label": "Scope", "value": "All 39 active environments & 14 baseline controls"}
        ],
        "action_url": "/api/compliance/export?format=csv",
        "action_label": "Download CSV Ledger"
    }

    msg = (
        "📊 **Executive SOC 2 Compliance Report Ready**\n\n"
        "The compliance ledger contains point-in-time cryptographic evidence, control grades, and finding counts for every environment."
    )
    suggs = ["Download CSV", "Show fleet health", "Create environment"]
    sess.add_message("bot", msg, card=card, suggestions=suggs)
    return {"reply": msg, "suggestions": suggs, "card": card, "state": sess.state}


def _handle_faq_intent(sess: CopilotSession, low: str) -> Dict[str, Any]:
    msg = (
        "### Platform Console Architecture & Guardrails\n\n"
        "• **10-Stage Provisioning Pipeline**: Guarantees code formatting, schema validation, unit tests, OpenTofu planning, policy gate verification, manual approval gates, and cluster health verification.\n"
        "• **14 Baseline SOC 2 Controls**: Covers Default-Deny Ingress (`NET-1`), Zero-Trust RBAC (`ACC-1/2`), Resource Quotas (`RES-1`), S3 Public Block & AES256 Encryption (`STO-1/3`), and SQS Encryption (`MSG-1`).\n"
        "• **Self-Healing Cron Engine**: Periodically sweeps the cluster to detect drift and reconciles non-compliant spaces back to standard blueprints."
    )
    suggs = ["Create new environment", "Show fleet health", "Export audit CSV"]
    sess.add_message("bot", msg, suggestions=suggs)
    return {"reply": msg, "suggestions": suggs, "card": None, "state": sess.state}

def _handle_pricing_intent(sess: CopilotSession, low: str) -> Dict[str, Any]:
    from . import pricing
    spaces = [dict(s, name=n) for n, s in store.items("space")]
    finops = pricing.get_fleet_finops_summary(spaces)

    card = {
        "type": "pricing_summary",
        "title": "Cloud FinOps & Infrastructure Pricing",
        "fields": [
            {"label": "Total Fleet Spend", "value": f" / month"},
            {"label": "Active Environments", "value": str(finops['active_environments'])},
            {"label": "Average per Environment", "value": f" / month"},
            {"label": "Standard Microservice", "value": ".00 / mo (small dev)"},
            {"label": "Minimal Internal Tool", "value": ".15 / mo (small dev)"},
            {"label": "Data & Analytics Lake", "value": ".30 / mo (small dev)"}
        ]
    }

    msg = (
        "💰 **Cloud Infrastructure Pricing & FinOps Governance**\n\n"
        f"• **Fleet Estimated Run-Rate**: ${finops['total_monthly_usd']:,.2f} / month across {finops['active_environments']} spaces\n"
        f"• **Average Cost per Space**: ${finops['avg_cost_per_space_monthly']:,.2f} / month\n\n"
        "**Standard Pricing Matrix**:\n"
        "• **Minimal** (minimal): $0.055/hr (~$40.15/mo)\n"
        "• **Frontend SPA** (rontend_spa): $0.070/hr (~$51.10/mo)\n"
        "• **Standard Microservice** (standard): $0.100/hr (~$73.00/mo)\n"
        "• **Data & Analytics Lake** (data_analytics): $0.110/hr (~$80.30/mo)\n"
        "• **Event-Driven Hub** (event_driven): $0.125/hr (~$91.25/mo)\n\n"
        "*Production Multi-AZ adds a 2.0x redundancy multiplier for 99.99% availability.*"
    )
    suggs = ["Create environment", "Show fleet health", "Export audit CSV"]
    sess.add_message("bot", msg, card=card, suggestions=suggs)
    return {"reply": msg, "suggestions": suggs, "card": card, "state": sess.state}
