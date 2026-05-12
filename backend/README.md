# TrustGate Backend

TrustGate is a FastAPI KYB intelligence layer for Squad-style merchant onboarding. It scores vendors, stores verification evidence, exposes dashboard routes, and mocks Squad merchant creation until real credentials are available.

The current backend is intentionally a hybrid AI system, not a fake "massive trained fraud model." It combines deterministic verification, classical NLP, lightweight ML, anomaly detection, and explainable risk scoring. External BVN/CAC/paid checks are not called by default.

## Quick Start

From Git Bash:

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

From PowerShell:

```powershell
cd C:\Users\USER\Desktop\TrustGate\backend
python -m venv .venv
.\.venv\Scripts\activate
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

## AI/ML Positioning

TrustGate does not use an LLM to make fraud decisions. That is deliberate.

Current decisioning is based on:

- deterministic checks for structured facts like RC numbers, NIN/BVN format, addresses, and document completeness,
- classical NLP for entity extraction and document consistency,
- lightweight supervised ML with Naive Bayes for document-language authenticity,
- unsupervised ML with Isolation Forest for onboarding anomaly prioritization,
- explainable weighted trust scoring.

Where an LLM can help later:

- generate compliance-officer explanations,
- summarize ambiguous risk signals,
- convert technical flags into plain language,
- assist human review.

Where an LLM should not be used:

- final fraud decisioning,
- deterministic compliance validation,
- BVN/CAC/TIN verification,
- mathematical trust-score calculation.

The honest product framing is:

```text
TrustGate uses a hybrid intelligence architecture combining deterministic verification,
heuristic risk scoring, lightweight NLP analysis, and anomaly detection. The system is
designed to evolve into a supervised ML fraud pipeline as labeled merchant outcomes,
chargebacks, compliance reviews, and transaction history accumulate.
```

## NLP Pipeline Implementation

The NLP engine lives in `app/services/nlp.py`. It replaces the earlier simple consistency checker with a full local document-language pipeline for TrustGate.

What was added:

- OCR text extraction and Unicode/whitespace normalization.
- NLTK-based tokenization, stopword removal, POS tagging, and safe stemming that avoids Nigerian proper names and structured codes.
- TF-IDF vectorization for document comparison.
- spaCy `en_core_web_sm` NER for organizations, people, places, dates, money, and numbers, with regex fallback if the model is unavailable.
- Nigerian business-document regex extraction for RC, BVN/NIN-like numbers, TIN, NGN amounts, phone numbers, dates, addresses, company names, and director names.
- Multi-method consistency checks:
  - cosine/TF-IDF for document text features,
  - RapidFuzz token-set ratio for names and addresses,
  - normalized exact match for RC numbers and other structured codes.
- Nigerian name-order handling, so `Folake Adeniyi` can match `Adeniyi Folake Blessing`.
- Linguistic anomaly detection for template text, fraud phrases, copy-paste signatures, numeric anomalies, and OCR confidence.
- Naive Bayes document-authenticity classifier using `MultinomialNB(alpha=1.0)` with explicit Laplacian smoothing logs.
- Structured `NLPResult`, `Flag`, `FlagSeverity`, and `ClassifierResult` schemas in `app/schemas/verification.py`.
- Production-style logs to stdout and `logs/nlp_pipeline.log`.

The old backend scorer still works because `check_consistency()` remains as a compatibility adapter. The full new entry point is:

```python
from app.services.nlp import run_nlp_pipeline
```

## Agentic Verification Layer

The backend now includes `app/services/agentic_verification.py`.

This is not traditional RAG. It is a local-first fact-check agent that takes structured facts from NLP and decides which verification tools should check each fact type.

Current local tools:

- `cac_registry_lookup`: checks submitted RC/business name against extracted document facts.
- `identity_verification`: checks BVN/NIN format, placeholder numeric patterns, and director-name agreement.
- `address_geocoder`: checks address specificity and document-address agreement.
- `web_footprint_check`: checks whether the vendor submitted a website or business email domain.
- `local_template_explainer`: produces compliance-friendly explanation text without calling an LLM.

Important: these tools do not call CAC, Dojah, Prembly, Google Maps, Google Search, or OpenAI. They are local heuristics designed around provider interfaces. Every result says whether an external call was used.

The agent returns:

- `agent_score`,
- tool-level results,
- explainable flags,
- external services used,
- recommended action,
- compliance-friendly explanation.

The main verification flow now calls this agent and stores its flags alongside NLP, identity, and anomaly flags.

Run the standalone agent demo:

```bash
python test_agentic_verification_demo.py
```

Expected high-level output:

```text
CLEAN LOCAL AGENT CHECK
AGENT SCORE: 100/100
RECOMMENDED ACTION: approve
EXTERNAL SERVICES USED: []

FRAUD LOCAL AGENT CHECK
AGENT SCORE: 35/100
RECOMMENDED ACTION: block
EXTERNAL SERVICES USED: []
```

## External Service Policy

External services are disabled by default:

```env
EXTERNAL_VERIFICATION_ENABLED=false
IDENTITY_PROVIDER=local
CAC_PROVIDER=local
LLM_EXPLANATION_PROVIDER=local_template
DOJAH_API_KEY=
PREMBLY_API_KEY=
OPENAI_API_KEY=
```

This means:

- no paid BVN/NIN lookup is called,
- no CAC provider is called,
- no Google Maps/Search provider is called,
- no LLM provider is called.

Production-ready integration points are present conceptually, but real provider calls should only be enabled after choosing a provider, adding credentials, and deciding what data is safe to send externally.

Good future providers:

- Dojah or Prembly for BVN/NIN checks,
- Prembly/CAC-style provider for CAC lookup,
- FIRS/public TIN lookup where available,
- Google Maps or HERE for address geocoding,
- Google Custom Search or SerpAPI for web footprint checks,
- OpenAI or another LLM provider only for explanation generation.

## Anomaly Detection Engine

`app/services/anomaly.py` now has two layers:

- deterministic heuristics for free email domains, weak phone numbers, and suspicious placeholder business names,
- an Isolation Forest model from scikit-learn for onboarding-profile outlier detection.

The Isolation Forest currently trains on a small synthetic merchant baseline. This is correct for a hackathon MVP because real fraud labels are not available yet. In production, the baseline should be replaced with historical merchant onboarding, compliance outcomes, chargebacks, disputes, and transaction behavior.

What to say if asked about training data:

```text
At MVP stage, we use rules-assisted and semi-supervised risk prioritization.
The architecture is ready for supervised fraud classification once historical
merchant outcomes and compliance review labels accumulate.
```

Do not claim production fraud accuracy from the synthetic baseline.

## Trust Score Engine

`app/services/scorer.py` now aggregates multiple intelligence sources:

- identity checks,
- NLP document consistency,
- anomaly heuristics and Isolation Forest,
- local agentic verification flags.

The score is weighted by signal source and severity. The final verification summary includes dominant signals so the dashboard can explain why a vendor was approved, blocked, or sent to manual review.

## NLP Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install NLTK assets:

```bash
python setup_nlp.py
```

Install the spaCy English model:

```bash
python -m spacy download en_core_web_sm
```

These have already been installed in the local `.venv` on this machine.

## How To Check It Works

Run the normal backend tests:

```bash
python -m pytest tests -q
```

Expected result:

```text
2 passed
```

Run the NLP demo:

```bash
python test_nlp_demo.py
```

Expected high-level output:

```text
TEST CASE 1: Clean vendor
FINAL SCORE: 89/100
FLAGS: 3 (0 critical)

TEST CASE 2: Fraud vendor
FINAL SCORE: 0/100
FLAGS: 15
SUMMARY: NLP reviewed 2 documents and found 9 critical fraud signal(s).
```

The full step-by-step NLP logs are written to:

```text
logs/nlp_pipeline.log
```

To confirm spaCy NER is installed:

```bash
python -c "import spacy; nlp=spacy.load('en_core_web_sm'); print(nlp.meta['name'], nlp.meta['version'])"
```

Expected result:

```text
core_web_sm 3.8.0
```

Run the local agent demo:

```bash
python test_agentic_verification_demo.py
```

Run the API verification flow manually:

```bash
uvicorn app.main:app --reload
```

Then visit:

```text
http://127.0.0.1:8000/docs
```

Use:

1. `POST /api/v1/vendors/` to create a vendor.
2. `POST /api/v1/verify/{vendor_id}` to run TrustGate scoring.
3. `GET /api/v1/verify/{vendor_id}` to inspect the result.
4. `GET /api/v1/verify/{vendor_id}/flags` to inspect individual flags.

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
python -m pytest tests -q
```
