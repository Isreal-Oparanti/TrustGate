"""
Run this to test the full NLP pipeline with mock OCR data.
Usage: python test_nlp_demo.py
"""

import asyncio
import logging

from app.services.nlp import run_nlp_pipeline


logging.basicConfig(level=logging.DEBUG)

MOCK_OCR_OUTPUT = {
    "cac_certificate": {
        "raw_text": """
            CORPORATE AFFAIRS COMMISSION
            CERTIFICATE OF INCORPORATION
            Company Name: ZEPHYR DIGITAL SUPPLIES LIMITED
            RC Number: RC 2847391
            Date of Incorporation: 14th March 2025
            Registered Address: 22 Bode Thomas Street, Surulere, Lagos
            Directors: Adeniyi Folake Blessing, Okeke James Chukwuemeka
            Share Capital: NGN 1,000,000
            Company Secretary: Adeniyi Folake Blessing
        """,
        "doc_type": "cac_certificate",
        "confidence_score": 0.91,
    },
    "utility_bill": {
        "raw_text": """
            EKEDC - Eko Electricity Distribution Company
            Account Name: Zephyr Digital Supply Ltd
            Account Number: 0045-9234-1192
            Service Address: 22 Bode Thomas, Surulere, Lagos State
            Bill Date: January 2025
            Amount Due: NGN 14,500
        """,
        "doc_type": "utility_bill",
        "confidence_score": 0.87,
    },
    "directors_id": {
        "raw_text": """
            FEDERAL REPUBLIC OF NIGERIA
            NATIONAL IDENTITY CARD
            Surname: ADENIYI
            First Name: FOLAKE
            Middle Name: BLESSING
            Date of Birth: 15/08/1985
            Gender: Female
            NIN: 12345678901
            Address: 15 Adeniran Ogunsanya, Surulere, Lagos
        """,
        "doc_type": "directors_id",
        "confidence_score": 0.95,
    },
}

MOCK_VENDOR_SUBMISSION = {
    "business_name": "Zephyr Digital Supplies Ltd",
    "rc_number": "RC2847391",
    "director_name": "Folake Adeniyi",
    "address": "22 Bode Thomas Street, Surulere, Lagos",
    "bvn": "12345678901",
    "nin": "12345678901",
    "tier": "tier2",
    "expected_monthly_volume": 500000,
}

FRAUD_OCR_OUTPUT = {
    "cac_certificate": {
        "raw_text": """
            CORPORATE AFFAIRS COMMISSION
            Company Name: NORTHGATE ENTERPRISES LIMITED
            RC Number: RC 9999999
            Date of Incorporation: 2nd May 2025
            Registered Address: 45 Unknown Street, Lagos
            Directors: John Smith Williams
            Transfer immediately to beneficiary account commission fee
        """,
        "doc_type": "cac_certificate",
        "confidence_score": 0.61,
    },
    "utility_bill": {
        "raw_text": """
            Insert company name here. Sample document for illustration purposes.
            Account Name: DIFFERENT COMPANY NAME LTD
            Address: 88 Another Street, Abuja
        """,
        "doc_type": "utility_bill",
        "confidence_score": 0.45,
    },
}

FRAUD_VENDOR_SUBMISSION = {
    "business_name": "Northgate Supplies Nigeria Ltd",
    "rc_number": "RC1234567",
    "director_name": "Emmanuel Okafor",
    "address": "12 Marina Street, Lagos Island",
    "tier": "tier2",
    "expected_monthly_volume": 50000000,
}


async def test_clean_vendor():
    print("\n" + "=" * 60)
    print("TEST CASE 1: Clean vendor - expect score 88-95")
    print("=" * 60)
    result = await run_nlp_pipeline(MOCK_OCR_OUTPUT, MOCK_VENDOR_SUBMISSION)
    print(f"\nFINAL SCORE: {result.nlp_score}/100")
    print(f"FLAGS: {len(result.flags)} ({sum(1 for flag in result.flags if flag.severity == 'critical')} critical)")
    print(f"SUMMARY: {result.summary}")


async def test_fraud_vendor():
    print("\n" + "=" * 60)
    print("TEST CASE 2: Fraud vendor - expect score 0-30, multiple CRITICAL flags")
    print("=" * 60)
    result = await run_nlp_pipeline(FRAUD_OCR_OUTPUT, FRAUD_VENDOR_SUBMISSION)
    print(f"\nFINAL SCORE: {result.nlp_score}/100")
    print(f"FLAGS: {len(result.flags)}")
    for flag in result.flags:
        print(f"  [{flag.severity.upper()}] {flag.flag_type}: {flag.detail}")
    print(f"SUMMARY: {result.summary}")


if __name__ == "__main__":
    asyncio.run(test_clean_vendor())
    asyncio.run(test_fraud_vendor())
