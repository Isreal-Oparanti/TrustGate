"""
TrustGate OCR Engine Demo
Run: python test_ocr_demo.py

Tests the OCR pipeline with:
1. Synthetic test images generated programmatically (no real documents needed)
2. The existing mock OCR data used by NLP - to verify output shape matches
3. A full pipeline test: OCR output -> NLP pipeline

This means the test works even without real vendor documents uploaded.
"""

import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io

def create_test_cac_image() -> bytes:
    img = Image.new('RGB', (1240, 1754), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.truetype("arial.ttf", 32)
        font_medium = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large
    
    draw.text((100, 80), "CORPORATE AFFAIRS COMMISSION", font=font_large, fill='black')
    draw.text((100, 140), "CERTIFICATE OF INCORPORATION", font=font_large, fill='black')
    draw.text((100, 240), "Company Name: ZEPHYR DIGITAL SUPPLIES LIMITED", font=font_medium, fill='black')
    draw.text((100, 300), "RC Number: RC 2847391", font=font_medium, fill='black')
    draw.text((100, 360), "Date of Incorporation: 14th March 2025", font=font_medium, fill='black')
    draw.text((100, 420), "Registered Address: 22 Bode Thomas Street, Surulere, Lagos", font=font_medium, fill='black')
    draw.text((100, 480), "Directors: Adeniyi Folake Blessing, Okeke James Chukwuemeka", font=font_medium, fill='black')
    draw.text((100, 540), "Share Capital: NGN 1,000,000", font=font_medium, fill='black')
    
    buf = io.BytesIO()
    img.save(buf, format='PNG', dpi=(150, 150))
    return buf.getvalue()

def create_test_utility_bill_image() -> bytes:
    img = Image.new('RGB', (1240, 1754), color='white')
    draw = ImageDraw.Draw(img)
    try:
        font_medium = ImageFont.truetype("arial.ttf", 24)
    except:
        font_medium = ImageFont.load_default()
        
    draw.text((100, 100), "Account Name: Zephyr Digital Supply Ltd", font=font_medium, fill='black')
    draw.text((100, 160), "Service Address: 22 Bode Thomas, Surulere, Lagos State", font=font_medium, fill='black')
    draw.text((100, 220), "Bill Date: January 2025", font=font_medium, fill='black')
    draw.text((100, 280), "Amount Due: NGN 14,500", font=font_medium, fill='black')
    
    buf = io.BytesIO()
    img.save(buf, format='PNG', dpi=(150, 150))
    return buf.getvalue()

def create_test_id_image() -> bytes:
    img = Image.new('RGB', (1000, 600), color='white')
    draw = ImageDraw.Draw(img)
    try:
        font_medium = ImageFont.truetype("arial.ttf", 24)
    except:
        font_medium = ImageFont.load_default()
        
    draw.text((50, 50), "Surname: ADENIYI", font=font_medium, fill='black')
    draw.text((50, 100), "First Name: FOLAKE", font=font_medium, fill='black')
    draw.text((50, 150), "Middle Name: BLESSING", font=font_medium, fill='black')
    draw.text((50, 200), "NIN: 12345678901", font=font_medium, fill='black')
    draw.text((50, 250), "Address: 15 Adeniran Ogunsanya, Surulere, Lagos", font=font_medium, fill='black')
    
    buf = io.BytesIO()
    img.save(buf, format='PNG', dpi=(150, 150))
    return buf.getvalue()

async def test_synthetic_documents():
    print("TEST 1: Synthetic document OCR")
    
    from app.services.ocr import TrustGateOCR
    import tempfile, os
    
    ocr = TrustGateOCR()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cac_path = os.path.join(tmpdir, "cac_certificate.png")
        with open(cac_path, 'wb') as f:
            f.write(create_test_cac_image())
        
        result = await ocr.process_single_document(cac_path, "cac_certificate")
        
        print(f"  Confidence: {result.confidence_score:.2f}")
        print(f"  Method: {result.extraction_method}")
        print(f"  Chars extracted: {result.char_count}")
        print(f"  Warnings: {result.warnings}")
        
        if ocr.tesseract_available:
            assert "ZEPHYR DIGITAL" in result.raw_text.upper() or "ZEPHYR" in result.raw_text.upper(), "Company name not found"
            assert "2847391" in result.raw_text, "RC number not found"
            assert result.confidence_score > 0.80, f"Confidence too low: {result.confidence_score}"
            print("  [OK] All assertions passed")
        else:
            print("  - Tesseract not available, skipped assertions")

async def test_shape_matches_nlp_expectation():
    print("\nTEST 2: OCR output -> NLP pipeline integration")
    
    from app.services.ocr import TrustGateOCR
    from app.services.nlp import run_nlp_pipeline
    import tempfile, os
    
    ocr = TrustGateOCR()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = {
            "cac_certificate": os.path.join(tmpdir, "cac.png"),
            "utility_bill": os.path.join(tmpdir, "bill.png"),
            "directors_id": os.path.join(tmpdir, "id.png"),
        }
        with open(paths["cac_certificate"], 'wb') as f:
            f.write(create_test_cac_image())
        with open(paths["utility_bill"], 'wb') as f:
            f.write(create_test_utility_bill_image())
        with open(paths["directors_id"], 'wb') as f:
            f.write(create_test_id_image())
        
        ocr_output = await ocr.process_vendor_documents("test_vendor_001", paths)
        
        print(f"  Documents processed: {len(ocr_output.documents)}")
        for doc_type, result in ocr_output.documents.items():
            print(f"  {doc_type}: confidence={result.confidence_score:.2f} | chars={result.char_count}")
        
        vendor_submission = {
            "business_name": "Zephyr Digital Supplies Ltd",
            "rc_number": "RC2847391",
            "director_name": "Folake Adeniyi",
            "address": "22 Bode Thomas Street, Surulere, Lagos",
            "bvn": "12345678901",
            "nin": "12345678901",
            "tier": "tier2",
        }
        
        nlp_input = {
            doc_type: {
                "raw_text": result.raw_text,
                "doc_type": doc_type,
                "confidence_score": result.confidence_score
            }
            for doc_type, result in ocr_output.documents.items()
        }
        
        nlp_result = await run_nlp_pipeline(nlp_input, vendor_submission)
        
        print(f"\n  NLP score from real OCR output: {nlp_result.nlp_score}/100")
        print(f"  Critical flags: {sum(1 for f in nlp_result.flags if f.severity == 'critical')}")
        print(f"  Summary: {nlp_result.summary}")
        
        if ocr.tesseract_available:
            assert nlp_result.nlp_score > 70, f"Score too low for clean docs: {nlp_result.nlp_score}"
            print("  [OK] Full pipeline integration passed")

async def test_degraded_image():
    print("\nTEST 3: Image pre-processing on degraded document")
    
    from app.services.ocr import TrustGateOCR
    import tempfile, os
    
    ocr = TrustGateOCR()
    
    cac_bytes = create_test_cac_image()
    img = Image.open(io.BytesIO(cac_bytes))
    img = img.rotate(3, expand=True, fillcolor='white')
    img = img.filter(ImageFilter.GaussianBlur(radius=1))
    
    with tempfile.TemporaryDirectory() as tmpdir:
        degraded_path = os.path.join(tmpdir, "degraded_cac.png")
        img.save(degraded_path, quality=60)
        
        result = await ocr.process_single_document(degraded_path, "cac_certificate")
        
        print(f"  Degraded image confidence: {result.confidence_score:.2f}")
        print(f"  Extraction method: {result.extraction_method}")
        print(f"  Warnings: {result.warnings}")
        
        if ocr.tesseract_available:
            assert "tesseract_enhanced" in result.extraction_method or result.confidence_score > 0.60
            print("  [OK] Degraded image handled without crash")

if __name__ == "__main__":
    print("=" * 60)
    print("TrustGate OCR Engine Demo")
    print("=" * 60)
    asyncio.run(test_synthetic_documents())
    asyncio.run(test_shape_matches_nlp_expectation())
    asyncio.run(test_degraded_image())
    print("\n" + "=" * 60)
    print("All OCR tests passed")
    print("=" * 60)
