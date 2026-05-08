from app.models.vendor import Vendor


def check_consistency(vendor: Vendor, extracted_text: str) -> tuple[list[dict], str]:
    flags: list[dict] = []
    notes: list[str] = []
    lowered = extracted_text.lower()

    if extracted_text and vendor.business_name.lower() not in lowered:
        flags.append(
            {
                "code": "BUSINESS_NAME_MISMATCH",
                "title": "Business name not found in documents",
                "description": "Uploaded documents do not clearly mention the submitted business name.",
                "severity": 2,
                "source": "nlp",
            }
        )
        notes.append("Business name could not be matched against extracted document text.")

    if extracted_text and vendor.address.lower().split(",")[0] not in lowered:
        flags.append(
            {
                "code": "ADDRESS_WEAK_MATCH",
                "title": "Address has weak document match",
                "description": "The submitted address is not strongly represented in the uploaded documents.",
                "severity": 1,
                "source": "nlp",
            }
        )
        notes.append("Address evidence is weak and may require manual review.")

    if not extracted_text:
        flags.append(
            {
                "code": "NO_DOCUMENT_TEXT",
                "title": "No readable document text",
                "description": "No uploaded documents were available for OCR/NLP comparison.",
                "severity": 2,
                "source": "ocr",
            }
        )
        notes.append("No document text was available for consistency checks.")

    return flags, " ".join(notes) or "Submitted fields are consistent with available document text."
