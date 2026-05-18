# TrustGate Backend

The TrustGate backend is a FastAPI service for merchant onboarding, AI-assisted verification, Squad payment integration, wallet/transfer operations, and behavioural transaction monitoring.

It is built for the Squad Hackathon 3.0 **Proof of Life** challenge. The backend focuses on a real financial-services trust problem: merchants can appear legitimate during onboarding but become risky after they start receiving payments.

## Backend Responsibilities

The backend handles:

- vendor registration and login,
- document upload and storage,
- OCR/NLP document processing,
- identity and business consistency checks,
- agentic verification and compliance summaries,
- trust score calculation,
- vendor approval/review/flagging,
- Squad merchant/payment/wallet/transfer integration,
- webhook ingestion,
- behavioural transaction monitoring,
- dashboard metrics and review queue data.

## Tech Stack

- FastAPI
- SQLAlchemy
- SQLite by default
- Pydantic schemas
- PyMuPDF / Tesseract hooks for OCR
- RapidFuzz for text similarity
- scikit-learn for anomaly scoring
- HTTPX for external/provider-style calls
- Squad API wrapper with mock mode


## Local Setup

From `backend/`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Useful URLs:

- `GET /health`
- `GET /docs`
- `GET /uploads/<vendor-folder>/<filename>` for demo-uploaded files

## Environment Variables

The backend works in local/mock mode by default. Add a `.env` file in `backend/` for custom configuration.

```env
APP_NAME=TrustGate API
APP_ENV=development
DATABASE_URL=sqlite:///./trustgate.db

SQUAD_MOCK_MODE=true
SQUAD_API_BASE_URL=https://sandbox-api-d.squadco.com
SQUAD_SECRET_KEY=
SQUAD_PARENT_BUSINESS_ID=
PAYMENT_CALLBACK_URL=http://localhost:3000/vendor

EXTERNAL_VERIFICATION_ENABLED=false
OPENAI_API_KEY=
DOJAH_APP_ID=
DOJAH_API_KEY=
GOOGLE_MAPS_API_KEY=
GOOGLE_API_KEY=
GOOGLE_CX=
```

### Important Policy

External provider failures must not be exposed to frontend users. Provider outages are operational metadata, not fraud evidence. The backend sanitizes public verification details so users see neutral review/verification language instead of registry/provider failure messages.

## Database Models

Main models:

- `Vendor` - merchant profile, business identity, settlement details, Squad merchant IDs.
- `Document` - uploaded documents and metadata.
- `Verification` - latest trust score, score breakdown, verdict, summary, external check cards.
- `Flag` - saved risk/compliance flags.
- `Payment` - customer payment records.
- `Wallet` and `WalletActivity` - vendor wallet account and movement history.
- `Transaction` - webhook/monitoring transaction records.

The app creates tables automatically on startup for the demo and applies lightweight column migrations in `app/main.py`.

## API Routes

### Vendors

Router: `app/routers/vendors.py`

Endpoints:

- `POST /api/v1/vendors/` - create merchant profile.
- `GET /api/v1/vendors/` - list merchants with latest verification score.
- `GET /api/v1/vendors/{vendor_id}` - get merchant details with latest score.
- `PATCH /api/v1/vendors/{vendor_id}/status` - approve/review/flag merchant.
- `POST /api/vendors/login` - vendor portal login.
- `GET /api/vendors/me` - current vendor profile.

### Documents

Router: `app/routers/documents.py`

Endpoints:

- `POST /api/v1/documents/upload/{vendor_id}` - upload one document.
- `GET /api/v1/documents/{vendor_id}` - list uploaded documents.

Supported document types:

- `cac_certificate`
- `utility_bill`
- `directors_id`
- `cac_form_cac2`
- `cac_form_cac7`
- `memart`
- `bank_statement`
- `business_registration`

### Verification

Router: `app/routers/verification.py`

Endpoints:

- `POST /api/v1/verify/{vendor_id}` - run verification.
- `GET /api/v1/verify/{vendor_id}` - fetch latest verification.
- `POST /api/v1/verify/{vendor_id}/rerun` - rerun verification.

Verification calls the scorer pipeline in `app/services/scorer.py`.

### Dashboard

Router: `app/routers/dashboard.py`

Endpoints:

- `GET /api/v1/dashboard/stats`
- `GET /api/v1/dashboard/queue`
- `GET /api/v1/dashboard/recent`

### Squad

Router: `app/routers/squad.py`

Endpoints:

- `POST /api/v1/squad/create-merchant`
- `POST /api/v1/squad/create-merchant/{vendor_id}`
- `POST /api/v1/squad/webhook`

This router connects merchant approval and webhook activity to Squad-style workflows.

### Payments

Router: `app/routers/payments.py`

Endpoints:

- `POST /api/payments/initiate`
- `GET /api/payments`
- `GET /api/payments/security-question`
- `GET /api/payments/{transaction_ref}`
- `POST /api/webhooks/squad`

### Transfers

Router: `app/routers/transfers.py`

Endpoints:

- `POST /api/transfers/account-lookup`
- `POST /api/transfers`
- `POST /api/transfers/requery`

The backend verifies the vendor security answer before sending money.

### Wallets

Router: `app/routers/wallets.py`

Endpoints:

- `POST /api/wallets`
- `GET /api/wallets/me`
- `GET /api/wallets/me/transactions`

### Transactions

Router: `app/routers/transactions.py`

Endpoints:

- `GET /api/v1/transactions/`
- `GET /api/v1/transactions/stats`

These power the behavioural monitoring page.

## Verification Pipeline

The core verification flow is in `app/services/scorer.py`.

High-level steps:

1. Load uploaded vendor documents.
2. Run OCR using `TrustGateOCR`.
3. Combine extracted document text.
4. Run identity checks using `verify_identity`.
5. Run document consistency checks using `check_consistency`.
6. Extract Nigerian business fields using `NigerianDocumentFieldExtractor`.
7. Run agentic verification using `run_agentic_verification`.
8. Run onboarding anomaly detection using `detect_anomalies`.
9. Convert all flags to a common scoring format.
10. Calculate weighted trust score and score breakdown.
11. Store `Verification` and `Flag` rows.

## Scoring Logic

Trust score is weighted across four buckets:

- Identity - BVN/NIN/director signals.
- Documents - OCR quality and document consistency.
- Business - RC, address, web presence, category and footprint signals.
- Behaviour - anomaly and transaction behaviour signals.

The scorer returns:

- `trust_score`
- `identity_score`
- `document_score`
- `business_score`
- `behaviour_score`
- `risk_level`
- `verdict`
- `summary`
- `external_checks`

Fraud-specific caps are included. For example, a Tier 2/Tier 3 business BVN that does not start with the expected verified-business prefix creates a critical signal and caps the score.

## AI / Data Intelligence Layer

TrustGate uses a hybrid intelligence architecture. It does not pretend to be a huge production fraud model trained on private banking data.

Current intelligence sources:

1. **OCR**
   - Extracts text from uploaded documents.
   - Supports image and PDF workflows.

2. **NLP/document consistency**
   - Extracts names, RC numbers, addresses, identity numbers, phones, dates, and business terms.
   - Uses fuzzy matching and structured regex extraction.

3. **Identity rules**
   - Checks BVN/NIN structure.
   - Checks business BVN pattern for higher-tier merchants.
   - Checks tier-specific registration requirements.

4. **Agentic verification**
   - Plans and executes verification tools.
   - Produces tool-level results and reviewer-friendly summaries.
   - Prevents LLM advisory flags from inventing risk where the underlying tool did not fail.

5. **Anomaly detection**
   - Uses heuristic signals and Isolation Forest-style onboarding outlier detection.
   - Flags unusual profiles for review prioritization.

6. **Behavioural transaction monitoring**
   - Scores how merchant behaviour changes after onboarding.

## Behavioural Transaction Monitoring

Service: `app/services/transaction_monitor.py`

Signals monitored:

- transaction velocity spike,
- expected monthly volume breakout,
- repeated round-number transactions,
- single-customer revenue concentration,
- odd-hour high-value activity,
- rapid 24-hour volume accumulation.

When risk is detected:

- transaction is marked flagged,
- flags are saved to the latest verification,
- behaviour score and trust score are reduced,
- serious stacked signals can flag/restrict the merchant.

This supports the core product insight:

> Merchant fraud can evolve after onboarding, so trust score must be dynamic.

## Squad Integration

Service: `app/services/squad_api.py`

TrustGate uses Squad workflows for:

- merchant/sub-merchant creation,
- payment initiation,
- payment verification,
- webhook signature validation,
- wallet operations,
- account lookup,
- transfers,
- merchant status updates.

Mock mode lets the demo run without live credentials:

```env
SQUAD_MOCK_MODE=true
```

In production, set credentials and disable mock mode.

## Demo Data

The frontend has two presets in `client/lib/merchantPresets.ts`:

- **Legit Merchant** - Hubmart-style business profile with stronger public business signals.
- **Fraud Merchant** - Sunshine-style profile with suspicious identity and document inconsistency.

These presets are for presentation speed. The backend still processes them through the same vendor/document/verification flow.

## Running Tests

From `backend/`:

```bash
python -m pytest tests -q
```

If you only need a quick syntax check:

```bash
python -m py_compile app/main.py app/services/scorer.py app/services/transaction_monitor.py
```


