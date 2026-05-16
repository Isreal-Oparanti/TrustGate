from app.models.vendor import Vendor


def verify_identity(vendor: Vendor) -> tuple[list[dict], str]:
    flags: list[dict] = []

    if not vendor.bvn.isdigit() or len(vendor.bvn) != 11:
        flags.append(
            {
                "code": "BVN_FORMAT_INVALID",
                "title": "BVN format failed",
                "description": "BVN should be an 11 digit number before it can pass external verification.",
                "severity": 3,
                "source": "identity",
            }
        )
    elif vendor.tier in {"tier2", "tier3"} and not vendor.bvn.startswith("22"):
        flags.append(
            {
                "code": "BUSINESS_BVN_PATTERN_MISMATCH",
                "title": "Business BVN pattern mismatch",
                "description": "Business BVN pattern does not match the expected verified merchant profile.",
                "severity": 4,
                "source": "identity",
            }
        )

    if not vendor.nin.isdigit() or len(vendor.nin) != 11:
        flags.append(
            {
                "code": "NIN_FORMAT_INVALID",
                "title": "NIN format failed",
                "description": "NIN should be an 11 digit number before it can pass external verification.",
                "severity": 3,
                "source": "identity",
            }
        )

    if vendor.tier == "tier3" and not vendor.rc_number:
        flags.append(
            {
                "code": "RC_REQUIRED",
                "title": "Registered company missing RC number",
                "description": "Tier 3 vendors need an RC number for CAC verification.",
                "severity": 3,
                "source": "identity",
            }
        )

    status = "mock_passed" if not flags else "mock_failed"
    return flags, status
