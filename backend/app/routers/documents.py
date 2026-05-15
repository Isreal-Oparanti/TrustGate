import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.document import Document
from app.models.vendor import Vendor
from app.schemas.document import DocumentOut
from app.utils.file_handler import save_upload
from app.utils.logger import ocr_log


router = APIRouter()

SUPPORTED_DOC_TYPES = {
    "cac_certificate",
    "utility_bill",
    "directors_id",
    "cac_form_cac2",
    "cac_form_cac7",
    "memart",
    "bank_statement",
    "business_registration",
}


def _upload_error(doc_type: str, status_code: int = 422) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": "Upload failed",
            "detail": "Supported formats: PDF, JPG, PNG. Max size: 10MB",
            "doc_type_received": doc_type,
        },
    )


@router.post("/upload/{vendor_id}", response_model=DocumentOut)
async def upload_document(
    vendor_id: str,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if doc_type not in SUPPORTED_DOC_TYPES:
        return _upload_error(doc_type)

    contents = await file.read()
    file_size_kb = max(1, round(len(contents) / 1024))
    await file.seek(0)
    ocr_log(
        f"\u2192 Document received: {doc_type} | {file.filename or 'document'} | "
        f"{file_size_kb}KB | vendor: {vendor_id}"
    )

    try:
        filename, path = await save_upload(vendor_id, file)
    except ValueError:
        return _upload_error(doc_type, status_code=400)

    document = Document(
        id=str(uuid.uuid4()),
        vendor_id=vendor_id,
        doc_type=doc_type,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        path=path,
        file_size_kb=file_size_kb,
    )
    db.add(document)

    db.commit()
    db.refresh(document)
    return document


@router.get("/{vendor_id}", response_model=list[DocumentOut])
def list_documents(vendor_id: str, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return (
        db.query(Document)
        .filter(Document.vendor_id == vendor_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
