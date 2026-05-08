# TrustGate Backend

TrustGate is a FastAPI KYB intelligence layer for Squad-style merchant onboarding. It scores vendors, stores verification evidence, exposes dashboard routes, and mocks Squad merchant creation until real credentials are available.

## Quick Start

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate (type this exactly)
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Python 3.13 users should use the current `requirements.txt` ranges so pip can choose compatible wheels.

Open:

- API health: http://127.0.0.1:8000/health
- Swagger docs: http://127.0.0.1:8000/docs

## Database

The default database is SQLite:

```env
DATABASE_URL=sqlite:///./trustgate.db
```

To use Postgres, change `DATABASE_URL` in `.env`, for example:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/trustgate
```

The app creates tables automatically on startup for the demo flow.

## Core Routes

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/api/v1/vendors/` | Create a vendor application |
| GET | `/api/v1/vendors/` | List vendors, with optional `status` and `tier` filters |
| GET | `/api/v1/vendors/{vendor_id}` | Get one vendor |
| PATCH | `/api/v1/vendors/{vendor_id}/status` | Compliance approval/block/review |
| DELETE | `/api/v1/vendors/{vendor_id}` | Delete a vendor |
| POST | `/api/v1/verify/{vendor_id}` | Run OCR, NLP, identity, anomaly, and trust scoring |
| GET | `/api/v1/verify/{vendor_id}` | Get latest verification |
| GET | `/api/v1/verify/{vendor_id}/flags` | List individual AI flags |
| POST | `/api/v1/verify/{vendor_id}/rerun` | Re-run verification |
| POST | `/api/v1/documents/upload/{vendor_id}` | Upload PDF/image/TXT documents |
| GET | `/api/v1/documents/{vendor_id}` | List uploaded documents |
| POST | `/api/v1/squad/webhook` | Receive Squad-like events |
| POST | `/api/v1/squad/create-merchant` | Create merchant after approval with `{ "vendor_id": "..." }` |
| POST | `/api/v1/squad/create-merchant/{vendor_id}` | Path-based shortcut for merchant creation |
| GET | `/api/v1/squad/merchant/{vendor_id}` | Check merchant status |
| GET | `/api/v1/dashboard/stats` | Dashboard totals and score averages |
| GET | `/api/v1/dashboard/queue` | Pending/review queue |
| GET | `/api/v1/dashboard/recent` | Recent verification activity |

## Test

```bash
pytest
```
