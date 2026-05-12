"""Test LLaMA with the fixed _call_llama function."""
import json
from app.services.agentic_verification import _call_llama, _safe_json_parse, PLANNING_SYSTEM_PROMPT

vendor = {
    "business_name": "Zephyr Digital Supplies Ltd",
    "bvn": "22222222222",
    "rc_number": "RC2847391",
    "address": "22 Bode Thomas Street, Surulere, Lagos",
    "tier": "tier2",
    "director_name": "Folake Adeniyi",
}

print("Calling LLaMA with fixed _call_llama...")
try:
    raw = _call_llama(PLANNING_SYSTEM_PROMPT, vendor, max_tokens=512)
    print(f"\nResponse ({len(raw)} chars):")
    print(raw[:500])
    
    parsed = _safe_json_parse(raw)
    if parsed:
        print(f"\n✅ JSON parsed successfully!")
        print(f"Has plan: {'plan' in parsed}")
        print(f"Plan is list: {isinstance(parsed.get('plan'), list)}")
        if isinstance(parsed.get('plan'), list):
            for step in parsed['plan']:
                print(f"  Step {step.get('step')}: {step.get('tool')}")
    else:
        print(f"\n❌ Could not parse as JSON")
except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {e}")
