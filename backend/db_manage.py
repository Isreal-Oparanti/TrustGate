"""
TrustGate Database Manager
Usage:
    python db_manage.py view          — View all entries
    python db_manage.py view vendors  — View only vendors
    python db_manage.py view docs     — View only documents
    python db_manage.py view results  — View only verifications
    python db_manage.py view flags    — View only flags
    python db_manage.py wipe          — Delete ALL data (fresh start)
    python db_manage.py wipe vendors  — Delete only vendors (cascades)
"""

import sys

from app.database import SessionLocal
from app.models.document import Document
from app.models.flag import Flag
from app.models.vendor import Vendor
from app.models.verification import Verification


def view(db, table: str = "all"):
    if table in ("all", "vendors"):
        vendors = db.query(Vendor).order_by(Vendor.created_at.desc()).all()
        print(f"\n{'='*70}")
        print(f"  📦 VENDORS ({len(vendors)})")
        print(f"{'='*70}")
        if vendors:
            print(f"  {'ID':<38} {'NAME':<30} {'TIER':<6} {'STATUS'}")
            print(f"  {'─'*36}   {'─'*28}   {'─'*4}   {'─'*8}")
            for v in vendors:
                print(f"  {v.id:<38} {v.business_name:<30} {v.tier:<6} {v.status}")
        else:
            print("  (empty)")

    if table in ("all", "docs"):
        docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
        print(f"\n{'='*70}")
        print(f"  📄 DOCUMENTS ({len(docs)})")
        print(f"{'='*70}")
        if docs:
            print(f"  {'ID':<38} {'VENDOR':<38} {'FILENAME'}")
            print(f"  {'─'*36}   {'─'*36}   {'─'*20}")
            for d in docs:
                print(f"  {d.id:<38} {d.vendor_id:<38} {d.filename}")
        else:
            print("  (empty)")

    if table in ("all", "results"):
        vfys = db.query(Verification).order_by(Verification.created_at.desc()).all()
        print(f"\n{'='*70}")
        print(f"  🔍 VERIFICATIONS ({len(vfys)})")
        print(f"{'='*70}")
        if vfys:
            print(f"  {'ID':<38} {'VENDOR':<38} {'SCORE':>5}  {'VERDICT'}")
            print(f"  {'─'*36}   {'─'*36}   {'─'*5}  {'─'*8}")
            for v in vfys:
                emoji = "✅" if v.verdict == "approved" else "⚠️" if v.verdict == "review" else "❌"
                print(f"  {v.id:<38} {v.vendor_id:<38} {v.trust_score:>5}  {emoji} {v.verdict}")
        else:
            print("  (empty)")

    if table in ("all", "flags"):
        flags = db.query(Flag).order_by(Flag.severity.desc()).all()
        print(f"\n{'='*70}")
        print(f"  🚩 FLAGS ({len(flags)})")
        print(f"{'='*70}")
        if flags:
            for f in flags:
                sev = f.severity or "?"
                emoji = "🔴" if sev == "3" else "🟠" if sev == "2" else "🟡" if sev == "1" else "⚪"
                print(f"  {emoji} [{sev}] {f.code or '?':<30} {(f.description or '')[:50]}")
        else:
            print("  (empty)")

    print()


def wipe(db, table: str = "all"):
    confirm = input(f"\n⚠️  This will DELETE {'ALL' if table == 'all' else table} data. Type 'yes' to confirm: ")
    if confirm.strip().lower() != "yes":
        print("Cancelled.")
        return

    if table in ("all", "flags"):
        count = db.query(Flag).delete()
        print(f"  🗑️  Deleted {count} flags")

    if table in ("all", "results"):
        count = db.query(Verification).delete()
        print(f"  🗑️  Deleted {count} verifications")

    if table in ("all", "docs"):
        count = db.query(Document).delete()
        print(f"  🗑️  Deleted {count} documents")

    if table in ("all", "vendors"):
        # Must delete related records first
        if table == "vendors":
            db.query(Flag).delete()
            db.query(Verification).delete()
            db.query(Document).delete()
        count = db.query(Vendor).delete()
        print(f"  🗑️  Deleted {count} vendors")

    db.commit()
    print("\n✅ Done! Database is clean.\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    command = args[0] if args else "view"
    table = args[1] if len(args) > 1 else "all"

    db = SessionLocal()
    try:
        if command == "view":
            view(db, table)
        elif command == "wipe":
            wipe(db, table)
        else:
            print(__doc__)
    finally:
        db.close()
