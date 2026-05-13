# TrustGate Backend

TrustGate is a FastAPI platform layer for onboarding vendors under one Squad business, giving each vendor payment collection, transfer, and virtual wallet capabilities.

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
| POST | `/api/vendors/` | Create a vendor under your platform as a Squad sub-merchant |
| GET | `/api/vendors/me` | Get current vendor by `X-Vendor-Id` |
| POST | `/api/wallets` | Create current vendor's Squad business virtual account |
| GET | `/api/wallets/me` | Get current vendor's wallet |
| GET | `/api/wallets/me/transactions` | Get current vendor wallet transactions |
| POST | `/api/payments/initiate` | Create payment ref for the current vendor, require security answer, call Squad initiate, return checkout URL |
| GET | `/api/payments/{transaction_ref}` | Verify and return current vendor's payment status |
| GET | `/api/payments/` | List current vendor's local payment history, optionally filtered by `status` |
| POST | `/api/webhooks/squad` | Validate Squad HMAC webhook, update payment status, run fraud monitoring |
| POST | `/api/transfers/account-lookup` | Confirm a recipient account before transfer |
| POST | `/api/transfers` | Send money from your Squad wallet to a bank account |
| POST | `/api/transfers/requery` | Re-query a transfer status |

## Squad Payments

Create a vendor/sub-merchant first:

```http
POST /api/vendors/
```

```json
{
  "business_name": "Demo Vendor Ltd",
  "rc_number": "RC-DEMO-001",
  "bvn": "12345678901",
  "nin": "10987654321",
  "email": "demo.vendor@example.com",
  "phone": "08012345678",
  "address": "12 Marina Road, Lagos",
  "settlement_account_name": "Demo Vendor Ltd",
  "settlement_account_number": "0123456789",
  "settlement_bank_code": "058",
  "settlement_bank": "GTBank",
  "payment_security_question": "What is your demo payment security answer?",
  "payment_security_answer": "demo123"
}
```

Payment API routes require the current vendor header:

```http
X-Vendor-Id: vendor_id_returned_from_sub_merchant_creation
```

Example initiate payload:

```json
{
  "amount": 250000,
  "customer_email": "customer@example.com",
  "customer_name": "Ada Lovelace",
  "security_answer": "your_dev_answer",
  "currency": "NGN",
  "callback_url": "http://localhost:3000/",
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
SQUAD_PARENT_BUSINESS_ID=SBHDTWL6SR
PAYMENT_CALLBACK_URL=https://your-client.example/payments/callback
PAYMENT_SECURITY_QUESTION=Your configured security question
PAYMENT_SECURITY_ANSWER_HASH=sha256_hex_of_the_expected_answer
```

`PAYMENT_SECURITY_ANSWER` is also supported for local development, but prefer the hash in shared environments.

## Test

```bash
pytest
```
