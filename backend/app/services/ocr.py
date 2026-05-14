import fitz              # pymupdf
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import numpy as np
import cv2               # opencv-python
import os, time, uuid, re, unicodedata
from pathlib import Path
from scipy import stats
from scipy import stats
from app.utils.logger import ocr_log
from app.schemas.verification import OCRResult, OCRBatchResult
from app.config import settings

TESSERACT_CONFIGS = {
    "default": "--psm 6 --oem 3",
    "directors_id": "--psm 6 --oem 3",
    "bank_statement": "--psm 3 --oem 3",
    "utility_bill": "--psm 4 --oem 3",
    "cac_certificate": "--psm 6 --oem 3",
    "lang": "eng"
}

class TrustGateOCR:
    """
    Multi-strategy OCR engine for Nigerian business documents.
    """
    MIN_CONFIDENCE_THRESHOLD = 0.70
    TARGET_DPI = 300
    
    def __init__(self):
        if settings.TESSERACT_PATH:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_PATH
        self.tesseract_available = True
        self._verify_tesseract_installation()
    
    def _verify_tesseract_installation(self):
        try:
            version = pytesseract.get_tesseract_version()
            ocr_log(f"Tesseract accessible: version {version}")
        except pytesseract.TesseractNotFoundError:
            ocr_log("Tesseract not found. Please install Tesseract-OCR. Check setup_ocr.py.", "warning")
            self.tesseract_available = False

    async def process_vendor_documents(
        self,
        vendor_id: str,
        document_paths: dict[str, str]
    ) -> OCRBatchResult:
        start_time = time.time()
        ocr_log(f"▶ OCR START — vendor: {vendor_id} | files: {len(document_paths)}")
        
        results = {}
        low_confidence_docs = []
        total_conf = 0
        
        for doc_type, path in document_paths.items():
            result = await self.process_single_document(path, doc_type)
            results[doc_type] = result
            total_conf += result.confidence_score
            if result.confidence_score < self.MIN_CONFIDENCE_THRESHOLD:
                low_confidence_docs.append(doc_type)
                
        processing_time_ms = int((time.time() - start_time) * 1000)
        avg_confidence = total_conf / len(results) if results else 0.0
        
        ocr_log(f"✓ OCR COMPLETE — {len(results)} documents | avg confidence: {avg_confidence:.2f} | total: {processing_time_ms/1000:.1f}s")
        
        return OCRBatchResult(
            vendor_id=vendor_id,
            documents=results,
            total_processing_time_ms=processing_time_ms,
            avg_confidence=avg_confidence,
            low_confidence_docs=low_confidence_docs
        )

    async def process_single_document(self, file_path: str, doc_type: str) -> OCRResult:
        start_time = time.time()
        file_ext = Path(file_path).suffix.lower()
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024) if os.path.exists(file_path) else 0
        ocr_log(f"── Processing: {os.path.basename(file_path)}")
        ocr_log(f"   File size: {file_size_mb:.2f}MB | Type: {file_ext}")
        
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File {file_path} not found")
                
            if file_ext == ".pdf":
                result = await self._process_pdf(file_path, doc_type)
            elif file_ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"]:
                result = await self._process_image(file_path, doc_type)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
        except Exception as e:
            ocr_log(f"   ✗ Extraction failed for {doc_type}: {str(e)}", "error")
            result = OCRResult(
                raw_text="",
                doc_type=doc_type,
                confidence_score=0.0,
                page_count=0,
                file_type=file_ext.strip('.'),
                extraction_method="failed",
                warnings=["extraction_failed", str(e)],
                char_count=0,
                processing_time_ms=0,
                corrections_applied=[]
            )
            
        processing_time_ms = int((time.time() - start_time) * 1000)
        result.processing_time_ms = processing_time_ms
        ocr_log(f"   ✓ {doc_type} complete — method: {result.extraction_method} | confidence: {result.confidence_score:.2f}")
        return result

    async def _process_pdf(self, file_path: str, doc_type: str) -> OCRResult:
        ocr_log("   Strategy: Checking for digital text layer...")
        doc = fitz.open(file_path)
        combined_text = ""
        total_conf = 0.0
        warnings = []
        methods_used = set()
        pages = len(doc)
        
        ocr_log(f"   Pages: {pages}")
        if pages == 0:
            warnings.append("empty_pdf")
            return OCRResult(
                raw_text="", doc_type=doc_type, confidence_score=0.0, page_count=0,
                file_type="pdf", extraction_method="failed", warnings=warnings,
                char_count=0, processing_time_ms=0, corrections_applied=[]
            )

        for i, page in enumerate(doc):
            text = page.get_text("text")
            if len(text.strip()) > 50:
                ocr_log(f"   Page {i+1}: {len(text)} chars extracted via PyMuPDF direct text → HIGH QUALITY")
                combined_text += text + "\n"
                total_conf += 1.0
                methods_used.add("pymupdf_text")
            else:
                ocr_log(f"   Page {i+1}: {len(text)} chars only → switching to Tesseract OCR for page {i+1}")
                if self.tesseract_available:
                    mat = fitz.Matrix(self.TARGET_DPI/72, self.TARGET_DPI/72)
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    page_res = self._run_tesseract_on_image(img, doc_type)
                    combined_text += page_res["text"] + "\n"
                    total_conf += page_res["confidence"]
                    methods_used.add(page_res["method"])
                    ocr_log(f"   Page {i+1} Tesseract confidence: {page_res['confidence']:.2f}")
                else:
                    ocr_log(f"   Page {i+1}: Tesseract unavailable, skipped OCR")
                    warnings.append("tesseract_unavailable")
                    
        doc.close()
        
        avg_conf = total_conf / pages if pages > 0 else 0.0
        method_str = "+".join(sorted(methods_used)) if methods_used else "none"
        
        normalized_text, corrections = self._normalise_text(combined_text)
        
        if avg_conf < 0.50:
            warnings.append("very_low_confidence")
            
        return OCRResult(
            raw_text=normalized_text,
            doc_type=doc_type,
            confidence_score=avg_conf,
            page_count=pages,
            file_type="pdf",
            extraction_method=method_str,
            warnings=warnings,
            char_count=len(normalized_text),
            processing_time_ms=0,
            corrections_applied=corrections
        )

    async def _process_image(self, file_path: str, doc_type: str) -> OCRResult:
        ocr_log("   Strategy: Image file → Tesseract OCR")
        warnings = []
        
        try:
            img = Image.open(file_path)
            # Load to prevent closed file issues
            img.load()
        except Exception as e:
            raise ValueError(f"Failed to open image: {str(e)}")

        current_dpi = img.info.get('dpi', (72, 72))[0]
        ocr_log(f"   DPI: {current_dpi} | Size: {img.width}x{img.height}")
        
        doc_warnings = self._detect_document_warnings(img, 1.0, doc_type)
        warnings.extend(doc_warnings)
        
        # --- IMAGE FORENSICS START ---
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        img_np = np.array(img)
        forensics_warnings = self._compute_image_forensics(img_np, file_size)
        warnings.extend(forensics_warnings)
        # --- IMAGE FORENSICS END ---
        
        if not self.tesseract_available:
            warnings.append("tesseract_unavailable")
            return OCRResult(
                raw_text="", doc_type=doc_type, confidence_score=0.0, page_count=1,
                file_type="image", extraction_method="failed", warnings=warnings,
                char_count=0, processing_time_ms=0, corrections_applied=[]
            )

        res = self._run_tesseract_on_image(img, doc_type)
        
        ocr_log(f"   Initial confidence: {res['confidence']:.2f}")
        
        if res['confidence'] < self.MIN_CONFIDENCE_THRESHOLD:
            ocr_log(f"   Initial confidence {res['confidence']:.2f} → below threshold ({self.MIN_CONFIDENCE_THRESHOLD})")
            ocr_log("   Applying pre-processing...")
            
            enhanced_img = self._enhance_image(img, doc_type, current_dpi)
            enhanced_res = self._run_tesseract_on_image(enhanced_img, doc_type, enhanced=True)
            
            if enhanced_res['confidence'] > res['confidence']:
                ocr_log(f"   Post-processing confidence: {enhanced_res['confidence']:.2f} → improved")
                res = enhanced_res
            else:
                ocr_log(f"   Post-processing confidence: {enhanced_res['confidence']:.2f} → not improved, using original")

        normalized_text, corrections = self._normalise_text(res['text'])
        
        if res['confidence'] < 0.50:
            warnings.append("very_low_confidence")

        return OCRResult(
            raw_text=normalized_text,
            doc_type=doc_type,
            confidence_score=res['confidence'],
            page_count=1,
            file_type="image",
            extraction_method=res['method'],
            warnings=warnings,
            char_count=len(normalized_text),
            processing_time_ms=0,
            corrections_applied=corrections
        )

    def _compute_image_forensics(self, img_np: np.ndarray, file_size: int) -> list[str]:
        warnings = []
        try:
            if len(img_np.shape) == 3:
                gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            else:
                gray = img_np
            
            # 1. Entropy
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist = hist.ravel() / hist.sum()
            # remove zeros to avoid log(0) warnings/nans
            hist = hist[hist > 0]
            entropy = float(stats.entropy(hist, base=2))
            
            # 2. Compression Ratio
            height, width = gray.shape
            compression_ratio = file_size / (width * height) if (width * height) > 0 else 0
            
            # 3. Edge density
            edges = cv2.Canny(gray, 100, 200)
            edge_density = float(np.count_nonzero(edges) / (width * height)) if (width * height) > 0 else 0
            
            ocr_log(f"   Image forensics: entropy={entropy:.2f} compression={compression_ratio:.4f} edges={edge_density:.4f}")
            
            if entropy > 7.5:
                warnings.append("high_entropy_edit_splice")
            if compression_ratio < 0.05:
                warnings.append("extreme_compression_resave")
                
        except Exception as e:
            ocr_log(f"   Forensics failed: {e}", "warning")
            
        return warnings

    def _run_tesseract_on_image(self, img: Image.Image, doc_type: str, enhanced: bool = False) -> dict:
        config = f"{TESSERACT_CONFIGS.get(doc_type, TESSERACT_CONFIGS['default'])} -l {TESSERACT_CONFIGS['lang']}"
        try:
            data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
            text = pytesseract.image_to_string(img, config=config)
            conf = self._calculate_confidence(data)
        except Exception as e:
            ocr_log(f"   Tesseract execution failed: {e}", "error")
            text = ""
            conf = 0.0
            
        return {
            "text": text,
            "confidence": conf,
            "method": "tesseract_enhanced" if enhanced else "tesseract"
        }

    def _enhance_image(self, img: Image.Image, doc_type: str, current_dpi: float) -> Image.Image:
        # Step 1: Greyscale
        img = img.convert('L')
        ocr_log("   Applied: Converted to greyscale")
        
        # Step 2: Upscale
        if current_dpi < 200 or current_dpi == 72:
            new_width = int(img.width * (self.TARGET_DPI / max(current_dpi, 72)))
            new_height = int(img.height * (self.TARGET_DPI / max(current_dpi, 72)))
            img = img.resize((new_width, new_height), Image.LANCZOS)
            ocr_log(f"   Applied: Upscaled to {self.TARGET_DPI} DPI")
            
        img_array = np.array(img)
        
        # Step 3: Deskew
        edges = cv2.Canny(img_array, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi/180, 200)
        if lines is not None:
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = np.degrees(theta)
                # Ensure angle is around 90
                if 45 < angle < 135:
                    angles.append(angle - 90)
            if angles:
                median_angle = np.median(angles)
                if 0.5 < abs(median_angle) < 15:
                    h, w = img_array.shape
                    M = cv2.getRotationMatrix2D((w/2, h/2), median_angle, 1)
                    img_array = cv2.warpAffine(img_array, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                    ocr_log(f"   Applied: Deskew detected angle {median_angle:.2f}° → corrected")
                else:
                    ocr_log(f"   Applied: Deskew detected angle {median_angle:.2f}° → skipped")
        
        # Step 6: CLAHE for ID cards
        if doc_type == "directors_id":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            img_array = clahe.apply(img_array)
            ocr_log("   Applied: CLAHE contrast enhancement for glare reduction")

        # Step 4: Adaptive thresholding
        img_array = cv2.adaptiveThreshold(
            img_array, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=10
        )
        ocr_log("   Applied: adaptive Gaussian thresholding")
        
        # Step 5: Noise removal
        kernel = np.ones((1,1), np.uint8)
        img_array = cv2.morphologyEx(img_array, cv2.MORPH_CLOSE, kernel)
        ocr_log("   Applied: Noise removal applied")
        
        return Image.fromarray(img_array)

    def _calculate_confidence(self, tesseract_data: dict) -> float:
        confs = tesseract_data.get('conf', [])
        texts = tesseract_data.get('text', [])
        
        valid_words = []
        for conf, text in zip(confs, texts):
            try:
                c = int(conf)
            except ValueError:
                continue
            if c > 0 and len(text.strip()) >= 2:
                valid_words.append((c, len(text.strip())))
                
        if not valid_words:
            return 0.0
            
        weighted_sum = sum(c * length for c, length in valid_words)
        total_length = sum(length for _, length in valid_words)
        
        if total_length == 0:
            return 0.0
            
        score = (weighted_sum / total_length) / 100.0
        
        # Penalty for short extraction
        if len(valid_words) < 20:
            score *= 0.8
            
        return max(0.0, min(1.0, score))

    def _normalise_text(self, raw_text: str) -> tuple[str, list[str]]:
        corrections = []
        
        text = unicodedata.normalize("NFKD", raw_text) if 'unicodedata' in globals() else raw_text
        text = "".join(char for char in text if char.isprintable() or char in "\n\t")
        
        # Multiple spaces/newlines
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        def track_sub(pattern, repl, t, name):
            new_t, count = re.subn(pattern, repl, t)
            if count > 0:
                corrections.append(f"{name} ({count})")
            return new_t
            
        # O to 0 in numeric
        text = track_sub(r'(?<=RC\s)[O]', '0', text, "RC_O_to_0")
        text = track_sub(r'\bO(?=\d{6})', '0', text, "Numeric_O_to_0")
        text = track_sub(r'(?<=\d)O(?=\d)', '0', text, "Numeric_O_to_0_mid")
        
        # l to 1 in numeric
        text = track_sub(r'(?<=\d)l(?=\d)', '1', text, "Numeric_l_to_1")
        text = track_sub(r'\bl(?=\d{6})', '1', text, "Numeric_l_to_1_start")
        
        # RG to RC
        text = track_sub(r'\bRG\b(?=\s*\d+)', 'RC', text, "RG_to_RC")
        
        # NGN errors
        text = track_sub(r'\b(?:NCN|NGM|NGH)\b', 'NGN', text, "NGN_correction")
        
        return text.strip(), corrections

    def _detect_document_warnings(self, img: Image.Image, confidence: float, doc_type: str) -> list[str]:
        warnings = []
        if img.width < 400 or img.height < 400:
            warnings.append("very_low_resolution")
            
        # White image check
        try:
            extrema = img.convert("L").getextrema()
            if extrema[0] >= 240:
                warnings.append("near_blank_document")
        except Exception:
            pass
            
        current_dpi = img.info.get('dpi', (72, 72))[0]
        if current_dpi in (72, 96):
            if (img.width, img.height) in [(1920, 1080), (1080, 1920), (1280, 720), (720, 1280), (750, 1334), (1170, 2532)]:
                warnings.append("possible_screenshot")
                
        return warnings
