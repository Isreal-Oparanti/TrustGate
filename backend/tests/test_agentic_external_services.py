from app.config import settings
from app.services import agentic_verification as agent


def test_external_agentic_services_success(monkeypatch):
    async def fake_get_json(url, *, params, headers=None):
        if url == agent.DOJAH_BVN_URL:
            return {
                "entity": {
                    "bvn": {"value": "22222222222", "status": True},
                    "first_name": "John",
                    "middle_name": "Anon",
                    "last_name": "Doe",
                    "phone_number": "08012345678",
                    "watch_listed": "NO",
                }
            }
        if url == agent.DOJAH_NIN_URL:
            return {
                "entity": {
                    "first_name": "John",
                    "middle_name": "Anon",
                    "last_name": "Doe",
                    "phone_number": "08012345678",
                }
            }
        if url == "https://nominatim.openstreetmap.org/search":
            return [
                {
                    "display_name": "3 MacGregor Road, Ikoyi, Lagos, Nigeria",
                    "class": "building",
                    "lat": "6.455",
                    "lon": "3.394"
                }
            ]
        if url == agent.GOOGLE_CUSTOM_SEARCH_URL:
            return {
                "searchInformation": {"totalResults": "4"},
                "items": [
                    {"link": "https://example.com/one"},
                    {"link": "https://example.com/two"},
                    {"link": "https://example.com/three"},
                ],
            }
        raise AssertionError(f"Unexpected URL: {url}")

    async def fake_post_text(url, *, form_data, headers=None):
        assert url == agent.CAC_SEARCH_URL
        return """
        <table>
          <tr>
            <td>RC2847391</td>
            <td>Dojah Sandbox Merchant Ltd</td>
            <td>2024-01-01</td>
            <td>Active</td>
          </tr>
        </table>
        """

    async def fake_post_json(url, *, json_payload=None, form_data=None, headers=None):
        assert url == agent.ANTHROPIC_MESSAGES_URL
        return {
            "content": [
                {
                    "type": "text",
                    "text": "The vendor has consistent identity, CAC, address, and footprint signals. No blocking issues were found in the verification tools.",
                }
            ]
        }

    monkeypatch.setattr(agent, "_get_json", fake_get_json)
    monkeypatch.setattr(agent, "_post_text", fake_post_text)
    monkeypatch.setattr(agent, "_post_json", fake_post_json)
    monkeypatch.setattr(settings, "EXTERNAL_VERIFICATION_ENABLED", True)
    monkeypatch.setattr(settings, "DOJAH_APP_ID", "sandbox_app")
    monkeypatch.setattr(settings, "DOJAH_API_KEY", "sandbox_key")
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "maps_key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "search_key")
    monkeypatch.setattr(settings, "GOOGLE_CX", "search_cx")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "anthropic_key")

    result = agent.run_agentic_verification(
        {
            "business_name": "Dojah Sandbox Merchant Ltd",
            "rc_number": "RC2847391",
            "director_name": "John Doe Anon",
            "address": "3 MacGregor Road, Ikoyi, Lagos",
            "bvn": "22222222222",
            "nin": "70123456789",
            "email": "ops@dojahsandbox.ng",
            "tier": "tier2",
        },
        {
            "rc_numbers": ["RC 2847391"],
            "company_names": ["Dojah Sandbox Merchant Limited"],
            "director_names": ["John Doe Anon"],
            "addresses": ["3 MacGregor Road, Ikoyi, Lagos"],
        },
    )

    assert result.external_services_used == [
        "dojah_bvn",
        "dojah_nin",
        "cac_public_registry",
        "nominatim_maps",
        "google_search",
        "claude_haiku",
    ]
    assert 85 <= result.agent_score <= 100
    assert result.recommended_action == "approve"
    assert not result.flags
