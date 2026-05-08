from app.models.vendor import Vendor


FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}


def detect_anomalies(vendor: Vendor) -> tuple[list[dict], str]:
    flags: list[dict] = []
    email_domain = vendor.email.split("@")[-1].lower() if "@" in vendor.email else ""

    if vendor.tier in {"tier2", "tier3"} and email_domain in FREE_EMAIL_DOMAINS:
        flags.append(
            {
                "code": "FREE_EMAIL_FOR_BUSINESS",
                "title": "Business uses free email domain",
                "description": "Higher-tier vendors using free email domains can require stronger footprint checks.",
                "severity": 1,
                "source": "anomaly",
            }
        )

    if len("".join(ch for ch in vendor.phone if ch.isdigit())) < 10:
        flags.append(
            {
                "code": "PHONE_WEAK_SIGNAL",
                "title": "Phone number is weak",
                "description": "Phone number has too few digits to be a reliable contact signal.",
                "severity": 2,
                "source": "anomaly",
            }
        )

    if vendor.business_name.lower() in {"test", "sample", "unknown"}:
        flags.append(
            {
                "code": "SUSPICIOUS_BUSINESS_NAME",
                "title": "Suspicious business name",
                "description": "The business name looks like placeholder data rather than a real merchant.",
                "severity": 2,
                "source": "anomaly",
            }
        )

    return flags, "Anomaly scan completed with behavioral and metadata heuristics."
