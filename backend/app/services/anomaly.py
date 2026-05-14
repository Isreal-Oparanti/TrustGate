from app.models.vendor import Vendor

try:
    from sklearn.ensemble import IsolationForest
except Exception:  # pragma: no cover - dependency fallback
    IsolationForest = None


FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}


def detect_anomalies(vendor: Vendor, ml_features: dict) -> tuple[list[dict], str]:
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

    ml_flag, ml_note = detect_registration_outlier(ml_features)
    if ml_flag:
        flags.append(ml_flag)

    return flags, f"Anomaly scan completed with behavioral heuristics and Isolation Forest signal. {ml_note}"


def generate_training_profiles() -> list[dict]:
    """
    Generate realistic synthetic Nigerian vendor profiles for training.
    150 legitimate + 50 fraudulent = 200 total.
    Features: registration_age_days, has_web_presence, address_specificity,
    share_capital_round, director_count, doc_confidence_avg,
    name_similarity_score, nin_bvn_format_valid, registration_to_payment_gap_days
    """
    import random
    profiles = []
    
    # Legitimate profiles
    for _ in range(150):
        profiles.append({
            "label": 0,  # legitimate
            "registration_age_days": random.randint(180, 3650),
            "has_web_presence": random.choice([0.8, 0.9, 1.0]),
            "address_specificity": random.uniform(0.7, 1.0),
            "share_capital_round": random.choice([0, 0, 0, 1]),
            "director_count": random.randint(1, 4),
            "doc_confidence_avg": random.uniform(0.75, 0.98),
            "name_similarity_score": random.uniform(0.80, 1.0),
            "nin_bvn_format_valid": 1,
            "registration_to_payment_gap_days": random.randint(30, 730),
        })
    
    # Fraudulent profiles
    for _ in range(50):
        profiles.append({
            "label": 1,  # fraudulent
            "registration_age_days": random.randint(1, 14),
            "has_web_presence": random.choice([0.0, 0.0, 0.1]),
            "address_specificity": random.uniform(0.0, 0.4),
            "share_capital_round": 1,
            "director_count": 1,
            "doc_confidence_avg": random.uniform(0.40, 0.65),
            "name_similarity_score": random.uniform(0.3, 0.65),
            "nin_bvn_format_valid": random.choice([0, 1]),
            "registration_to_payment_gap_days": random.randint(0, 7),
        })
    
    return profiles


def detect_registration_outlier(ml_features: dict) -> tuple[dict | None, str]:
    """
    Empirical unsupervised ML for MVP anomaly detection.
    Trains dynamically on domain-specific synthetic profiles to establish boundaries.
    """
    from app.utils.logger import db_log
    
    if not IsolationForest:
        return None, "Isolation Forest unavailable; skipped ML anomaly signal."

    # Generate training data and extract features into list format
    training_data = generate_training_profiles()
    features_keys = [
        "registration_age_days", "has_web_presence", "address_specificity",
        "share_capital_round", "director_count", "doc_confidence_avg",
        "name_similarity_score", "nin_bvn_format_valid", "registration_to_payment_gap_days"
    ]
    
    baseline = []
    for profile in training_data:
        baseline.append([float(profile[k]) for k in features_keys])

    # Extract target features in matching order
    target_feature = [float(ml_features.get(k, 0.0)) for k in features_keys]

    model = IsolationForest(contamination=0.25, n_estimators=100, random_state=42)
    model.fit(baseline)
    
    threshold = model.offset_
    
    db_log(f"Isolation Forest training: {len(training_data)} profiles (150 legitimate, 50 fraudulent)")
    db_log(f"Contamination rate: 0.25 | n_estimators: 100")
    db_log(f"Features: {features_keys}")
    db_log(f"Training complete — anomaly threshold: {threshold:.4f}")
    
    db_log(f"Isolation Forest input features: {ml_features}")

    prediction = int(model.predict([target_feature])[0])
    decision_score = float(model.decision_function([target_feature])[0])
    
    decision = "anomalous" if prediction == -1 else "normal"
    db_log(f"Isolation Forest anomaly score: {decision_score:.4f} | decision: {decision}")

    if prediction == -1:
        return (
            {
                "code": "ML_REGISTRATION_OUTLIER",
                "title": "Registration profile is an ML outlier",
                "description": (
                    "Isolation Forest marked this onboarding profile as unusual compared with "
                    "known legitimate and fraudulent Nigerian vendor profiles. This is a prioritization signal."
                ),
                "severity": 2,
                "source": "anomaly_ml",
            },
            f"Isolation Forest score={decision_score:.4f}; prediction=outlier.",
        )

    return None, f"Isolation Forest score={decision_score:.4f}; prediction=inlier."
