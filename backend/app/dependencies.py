from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.vendor import Vendor


def get_current_vendor(
    x_vendor_id: str | None = Header(default=None, alias="X-Vendor-Id"),
    db: Session = Depends(get_db),
) -> Vendor:
    if not x_vendor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Vendor-Id header is required",
        )

    vendor = db.query(Vendor).filter(Vendor.id == x_vendor_id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current vendor was not found",
        )
    return vendor
