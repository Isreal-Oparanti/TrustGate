import pytesseract
from pathlib import Path
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

tesseract_path = os.getenv("TESSERACT_PATH")
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

print("Checking Tesseract installation...")
try:
    version = pytesseract.get_tesseract_version()
    print(f"[OK] Tesseract found: version {version}")
except pytesseract.TesseractNotFoundError:
    print("[FAIL] Tesseract not found.")
    print("")
    print("Install instructions:")
    print("  Windows: Download installer from https://github.com/UB-Mannheim/tesseract/wiki")
    print("  Mac:     brew install tesseract")
    print("  Ubuntu:  sudo apt install tesseract-ocr tesseract-ocr-eng")
    print("")
    print("After installing, set path in your .env:")
    print("  TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe  (Windows)")
    exit(1)

# Check English language pack
try:
    cmd = [tesseract_path or 'tesseract', '--list-langs']
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    if 'eng' not in result.stdout + result.stderr:
        print("[FAIL] English language pack missing")
        print("  Ubuntu: sudo apt install tesseract-ocr-eng")
        exit(1)
except Exception as e:
    print(f"[FAIL] Could not verify language packs: {e}")
    exit(1)

print("[OK] English language pack: installed")
print("[OK] OCR setup complete")
