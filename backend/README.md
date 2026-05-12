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
| POST | `/api/payments/initiate` | Create payment ref for the current vendor, require security answer, call Squad initiate, return checkout URL |
| GET | `/api/payments/{transaction_ref}` | Verify and return current vendor's payment status |
| GET | `/api/payments/` | List current vendor's local payment history, optionally filtered by `status` |
| GET | `/api/payments/squad-history` | Query current vendor's Squad transaction history by `reference`, with `start_date`, `end_date`, `currency`, `page`, and `perpage` |
| POST | `/api/webhooks/squad` | Validate Squad HMAC webhook, update payment status, run fraud monitoring |
| GET | `/api/v1/dashboard/stats` | Dashboard totals and score averages |
| GET | `/api/v1/dashboard/queue` | Pending/review queue |
| GET | `/api/v1/dashboard/recent` | Recent verification activity |

## Squad Payments

Payment API routes require the current vendor header:

```http
X-Vendor-Id: vendor_uuid_here
```

Example initiate payload:

```json
{
  "amount": 250000,
  "customer_email": "customer@example.com",
  "customer_name": "Ada Lovelace",
  "security_answer": "your_dev_answer",
  "currency": "NGN",
  "callback_url": "http://localhost:3000/payments/callback",
  "payment_channels": ["card", "bank", "ussd", "transfer"],
  "metadata": {
    "order_id": "ORD-1001"
  },
  "pass_charge": false
}
```

Set these environment values when leaving mock mode:

```env
SQUAD_MOCK_MODE=false
SQUAD_SECRET_KEY=sandbox_sk_or_live_sk
SQUAD_API_BASE_URL=https://sandbox-api-d.squadco.com
PAYMENT_CALLBACK_URL=https://your-client.example/payments/callback
PAYMENT_SECURITY_QUESTION=Your configured security question
PAYMENT_SECURITY_ANSWER_HASH=sha256_hex_of_the_expected_answer
```

`PAYMENT_SECURITY_ANSWER` is also supported for local development, but prefer the hash in shared environments.

## Test

```bash
pytest
```
