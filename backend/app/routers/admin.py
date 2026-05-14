from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vendor import Vendor
from app.schemas.vendor import VendorOut
from app.utils.logger import db_log


router = APIRouter()


@router.get("/vendors", response_model=list[VendorOut])
def list_admin_vendors(db: Session = Depends(get_db)):
    return db.query(Vendor).order_by(Vendor.created_at.desc()).all()


@router.delete("/vendors/{vendor_id}", status_code=204)
def delete_admin_vendor(vendor_id: str, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    db_log(f"Admin deleting vendor: {vendor.business_name} | id: {vendor.id}")
    db.delete(vendor)
    db.commit()
