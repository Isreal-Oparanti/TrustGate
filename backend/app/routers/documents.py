import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.document import Document
from app.models.vendor import Vendor
from app.schemas.document import DocumentOut
from app.utils.file_handler import save_upload


router = APIRouter()


@router.post("/upload/{vendor_id}", response_model=list[DocumentOut], status_code=201)
async def upload_documents(
    vendor_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    documents: list[Document] = []
    for file in files:
        try:
            filename, path = await save_upload(vendor_id, file)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        document = Document(
            id=str(uuid.uuid4()),
            vendor_id=vendor_id,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            path=path,
        )
        db.add(document)
        documents.append(document)

    db.commit()
    for document in documents:
        db.refresh(document)
    return documents


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
