"""
spaces.pricing
~~~~~~~~~~~~~~
FinOps & Cloud Cost Governance Engine for Kubernetes & AWS infrastructure.
Calculates real-time hourly and monthly costs, budget quotas, and cost attribution per team.
"""

# Cost per hour in USD (benchmarked against AWS us-east-1 standard on-demand pricing)
COST_MODELS = {
    "sizes": {
        "small": {
            "vcpu": 0.5,
            "memory_gb": 1.0,
            "hourly": 0.045,    # ~.85/month (EKS worker node slice + baseline quota)
            "desc": "0.5 vCPU / 1GB RAM slice"
        },
        "medium": {
            "vcpu": 2.0,
            "memory_gb": 4.0,
            "hourly": 0.180,    # ~.40/month
            "desc": "2.0 vCPU / 4GB RAM slice"
        },
        "large": {
            "vcpu": 4.0,
            "memory_gb": 8.0,
            "hourly": 0.360,    # ~.80/month
            "desc": "4.0 vCPU / 8GB RAM slice"
        }
    },
    "blueprints": {
        "minimal": {
            "name": "Minimal / Internal Tool",
            "hourly_base": 0.010,  # Logs & basic telemetry (.30/mo)
            "aws_services": ["logs"]
        },
        "frontend_spa": {
            "name": "Static Web / Frontend",
            "hourly_base": 0.025,  # S3 hosting, egress + logs (.25/mo)
            "aws_services": ["s3", "logs"]
        },
        "data_analytics": {
            "name": "Data & Analytics Lake",
            "hourly_base": 0.065,  # S3 AES256 Lake, KMS encryption, Secrets (.45/mo)
            "aws_services": ["s3", "secrets", "logs"]
        },
        "standard": {
            "name": "Standard Microservice",
            "hourly_base": 0.055,  # S3 + SQS + Secrets + Logs + IRSA (.15/mo)
            "aws_services": ["s3", "sqs", "secrets", "logs"]
        },
        "event_driven": {
            "name": "Event-Driven Hub",
            "hourly_base": 0.080,  # Encrypted SQS FIFO/SSE + S3 + Logs (.40/mo)
            "aws_services": ["s3", "sqs", "secrets", "logs"]
        }
    },
    "tiers": {
        "dev": {"multiplier": 1.0, "sla": "99.5%", "backup": "Daily"},
        "test": {"multiplier": 1.2, "sla": "99.9%", "backup": "6-hour snapshot"},
        "prod": {"multiplier": 2.0, "sla": "99.99% Multi-AZ", "backup": "Continuous replication & Multi-AZ"}
    }
}

HOURS_PER_MONTH = 730


def calculate_cost(size: str = "small", blueprint: str = "standard", tier: str = "dev", services: list = None) -> dict:
    size_cfg = COST_MODELS["sizes"].get(size, COST_MODELS["sizes"]["small"])
    bp_cfg = COST_MODELS["blueprints"].get(blueprint, COST_MODELS["blueprints"]["standard"])
    tier_cfg = COST_MODELS["tiers"].get(tier, COST_MODELS["tiers"]["dev"])

    base_hourly = size_cfg["hourly"] + bp_cfg["hourly_base"]
    total_hourly = round(base_hourly * tier_cfg["multiplier"], 4)
    monthly_estimate = round(total_hourly * HOURS_PER_MONTH, 2)

    return {
        "hourly": total_hourly,
        "monthly": monthly_estimate,
        "breakdown": {
            "compute_k8s_hourly": size_cfg["hourly"],
            "aws_services_hourly": bp_cfg["hourly_base"],
            "tier_multiplier": tier_cfg["multiplier"],
            "tier_sla": tier_cfg["sla"],
            "resources": {
                "vcpu": size_cfg["vcpu"],
                "memory_gb": size_cfg["memory_gb"],
                "services": services or bp_cfg["aws_services"]
            }
        }
    }


def get_fleet_finops_summary(spaces: list) -> dict:
    total_monthly = 0.0
    by_team = {}
    by_tier = {"dev": 0.0, "test": 0.0, "prod": 0.0}

    for s in spaces:
        req = s.get("request", {}) if isinstance(s, dict) else {}
        size = req.get("size", s.get("size", "small"))
        bp = req.get("blueprint", "standard")
        tier = req.get("environment", s.get("environment", "dev"))
        team = req.get("team", s.get("team", "unassigned"))

        cost_info = calculate_cost(size=size, blueprint=bp, tier=tier)
        m_cost = cost_info["monthly"]

        total_monthly += m_cost
        by_team[team] = round(by_team.get(team, 0.0) + m_cost, 2)
        by_tier[tier] = round(by_tier.get(tier, 0.0) + m_cost, 2)

    return {
        "total_monthly_usd": round(total_monthly, 2),
        "active_environments": len(spaces),
        "avg_cost_per_space_monthly": round(total_monthly / (len(spaces) or 1), 2),
        "spend_by_team": by_team,
        "spend_by_tier": by_tier
    }
