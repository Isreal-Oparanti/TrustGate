from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from app.config import settings
from app.utils.logger import logger


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"}


def ensure_upload_dir() -> Path:
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def safe_filename(filename: str) -> str:
    name = Path(filename).name.replace(" ", "_")
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported document type. Use PDF, image, WEBP, or TXT.")
    return f"{uuid4()}_{name}"


async def save_upload(vendor_id: str, file: UploadFile) -> tuple[str, str]:
    upload_dir = ensure_upload_dir() / vendor_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(file.filename or "document")
    path = upload_dir / filename
    contents = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise ValueError(f"File is larger than {settings.MAX_UPLOAD_MB}MB")
    path.write_bytes(contents)
    logger.info("📄 Saved uploaded document: %s", path)
    return filename, str(path)


def read_text_file(path: str) -> str:
    file_path = Path(path)
    if file_path.suffix.lower() != ".txt":
        return ""
    return file_path.read_text(encoding="utf-8", errors="ignore")
