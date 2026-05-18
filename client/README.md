# TrustGate Frontend

The TrustGate frontend is a Next.js application for two user groups:

- **Compliance/risk officers** who review merchants, inspect trust scores, and manage onboarding decisions.
- **Approved vendors** who receive money, initiate payment links, and send transfers from the vendor portal.

The interface is intentionally operational rather than decorative. It is designed for scanning risk signals, comparing merchants, and taking quick actions during a live demo.

## Tech Stack

- Next.js 14 App Router
- TypeScript
- SWR for client-side data fetching
- React Hot Toast for feedback
- Lucide React icons
- Utility-first CSS through `app/globals.css`

## Main Routes

```text
/dashboard          Overview metrics, average trust score, recent activity, review queue
/vendors            Merchant list with latest verification score and status
/vendors/new        Merchant onboarding, presets, document upload, verification trigger
/vendors/[id]       Merchant verification detail and approve/flag actions
/operations         Operational payment/wallet controls
/transactions       Behavioural transaction monitoring feed
/vendor/login       Vendor login
/vendor             Vendor portal for wallet, payments, transfers, activity
/checkout/[ref]     Payment checkout status page
```


## Design System

TrustGate uses a quiet fintech/compliance visual style:

- dark teal: `#0B3142`
- Squad pink accent: `#E51E56`
- success green: `#0D9B68`
- warning amber: `#D97706`
- danger red: `#DC2626`
- light background: `#F8F9FA`

Cards, badges, score rings, and signal lists follow the same visual language so judges can quickly understand risk levels.

## Frontend Features

### Compliance Dashboard

The dashboard shows:

- total vendors,
- approved/review/flagged counts,
- average trust score,
- recent verification activity,
- vendor review queue.

Data comes from:

- `GET /api/v1/dashboard/stats`
- `GET /api/v1/dashboard/queue`
- `GET /api/v1/dashboard/recent`

### Vendor Onboarding

The `/vendors/new` page collects:

- business name,
- RC number,
- director name,
- business category,
- website/social presence,
- expected monthly volume,
- BVN/NIN,
- contact and address details,
- settlement bank details,
- payment security question and answer,
- required documents.

The page supports two demo presets:

- **Legit Merchant** - Hubmart-style profile with strong public business signals.
- **Fraud Merchant** - Sunshine-style profile with suspicious identity and document inconsistencies.

On submission, the frontend:

1. Creates a vendor.
2. Uploads documents.
3. Starts AI verification.
4. Polls until the verification result is available.
5. Shows score, verdict, and next actions.

### Vendor Detail Page

The `/vendors/[id]` page shows:

- score ring,
- verdict badge,
- score breakdown,
- AI compliance summary,
- verification signals,
- verification check cards,
- address/contact/Squad account metadata,
- actions to rerun verification, approve, or flag a vendor.

The page sanitizes provider/error wording so users do not see internal external-service failures.

### Transaction Monitoring

The `/transactions` page shows live payment behaviour:

- total volume,
- transaction count,
- flagged count,
- suspended count,
- top merchants,
- transaction feed with risk badges.

This supports the core pitch that TrustGate monitors risk after onboarding.

### Vendor Portal

The `/vendor` page allows an approved vendor to:

- view wallet account details,
- copy virtual account number,
- create payment links,
- check payment status,
- send money through a confirmation modal,
- view wallet activity.

The send money flow uses one **Proceed** button. It performs account lookup, opens a modal with resolved transfer details, then sends the transfer after confirmation.

## API Client

All frontend backend calls are centralized in `client/lib/api.ts`.

Important functions:

- `createVendor`
- `uploadDocument`
- `runVerification`
- `getVerification`
- `updateVendorStatus`
- `getStats`
- `getQueue`
- `getTransactions`
- `initiatePayment`
- `lookupTransferAccount`
- `initiateTransfer`

`NEXT_PUBLIC_API_URL` controls the backend base URL.

Default:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Local Development

Install dependencies:

```bash
npm install
```

Run dev server:

```bash
npm run dev
```

Production build:

```bash
npm run build
```

## Demo Notes

For the hackathon presentation, start with the admin flow:

1. Open `/vendors/new`.
2. Load Legit Merchant.
3. Submit and show a good trust score.
4. Load Fraud Merchant.
5. Submit and show flags and lower score.
6. Open `/transactions` to show behavioural risk monitoring.
7. Open `/vendor` to show payment and transfer operations.


