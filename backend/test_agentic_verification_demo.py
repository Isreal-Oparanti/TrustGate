"""Run the local-first and external agentic verification demo cases."""

from app.config import settings
from app.services.agentic_verification import run_agentic_verification


CLEAN_VENDOR = {
    "business_name": "Zephyr Digital Supplies Ltd",
    "rc_number": "RC2847391",
    "director_name": "Folake Adeniyi",
    "address": "22 Bode Thomas Street, Surulere, Lagos",
    "bvn": "22345678901",
    "nin": "32345678901",
    "email": "ops@zephyrdigital.ng",
    "tier": "tier2",
}

CLEAN_FIELDS = {
    "rc_numbers": ["RC 2847391"],
    "company_names": ["Zephyr Digital Supplies Limited", "Zephyr Digital Supply Ltd"],
    "director_names": ["Adeniyi Folake Blessing"],
    "addresses": ["22 Bode Thomas Street, Surulere, Lagos"],
}

FRAUD_VENDOR = {
    "business_name": "Northgate Supplies Nigeria Ltd",
    "rc_number": "RC1234567",
    "director_name": "Emmanuel Okafor",
    "address": "12 Marina Street, Lagos Island",
    "bvn": "12345678901",
    "nin": "11111111111",
    "email": "northgate@gmail.com",
    "tier": "tier2",
}

FRAUD_FIELDS = {
    "rc_numbers": ["RC 9999999"],
    "company_names": ["Different Company Name Ltd"],
    "director_names": ["John Smith Williams"],
    "addresses": ["88 Another Street, Abuja"],
}

EXTERNAL_VENDOR = {
    "business_name": "Dojah Sandbox Merchant Ltd",
    "rc_number": "RC2847391",
    "director_name": "John Doe Anon",
    "address": "3 MacGregor Road, Ikoyi, Lagos",
    "bvn": "22222222222",
    "nin": "70123456789",
    "email": "ops@dojahsandbox.ng",
    "tier": "tier2",
}

EXTERNAL_FIELDS = {
    "rc_numbers": ["RC 2847391"],
    "company_names": ["Dojah Sandbox Merchant Limited"],
    "director_names": ["John Doe Anon"],
    "addresses": ["3 MacGregor Road, Ikoyi, Lagos"],
}

REQUIRED_EXTERNAL_CONFIG = (
    "NVIDIA_API_KEY",
    "DOJAH_APP_ID",
    "DOJAH_API_KEY",
    "GOOGLE_MAPS_API_KEY",
)


def show(label: str, vendor: dict, fields: dict) -> None:
    result = run_agentic_verification(vendor, fields)
    print("\n" + "=" * 60)
    print(label)
    print("=" * 60)
    print(f"AGENT SCORE: {result.agent_score}/100")
    print(f"RECOMMENDED ACTION: {result.recommended_action}")
    print(f"EXTERNAL SERVICES USED: {result.external_services_used}")
    print(f"EXPLANATION: {result.explanation}")
    print("TOOL RESULTS:")
    for tool in result.tools_called:
        print(f"  - {tool.tool_name}: {tool.status} ({tool.confidence}) via {tool.provider}")
    print("FLAGS:")
    for flag in result.flags:
        print(f"  - [{flag.severity.upper()}] {flag.flag_type}: {flag.detail}")


def external_demo_ready() -> tuple[bool, list[str]]:
    missing = [name for name in REQUIRED_EXTERNAL_CONFIG if not getattr(settings, name)]
    return settings.EXTERNAL_VERIFICATION_ENABLED and not missing, missing


def show_external_case() -> None:
    ready, missing = external_demo_ready()
    if not ready:
        print("\n" + "=" * 60)
        print("EXTERNAL SERVICES ENABLED AGENT CHECK")
        print("=" * 60)
        print("SKIPPED: set EXTERNAL_VERIFICATION_ENABLED=true and configure:")
        print(f"  {', '.join(missing) if missing else 'external verification flag'}")
        return
    show("EXTERNAL SERVICES ENABLED AGENT CHECK", EXTERNAL_VENDOR, EXTERNAL_FIELDS)


if __name__ == "__main__":
    show("CLEAN LOCAL AGENT CHECK", CLEAN_VENDOR, CLEAN_FIELDS)
    show("FRAUD LOCAL AGENT CHECK", FRAUD_VENDOR, FRAUD_FIELDS)
    show_external_case()
