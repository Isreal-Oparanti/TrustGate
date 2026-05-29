import type {
  DashboardStats,
  Flag,
  PaymentInitiateRequest,
  PaymentInitiateResponse,
  PaymentLookupResponse,
  PaymentRecord,
  PaymentSecurityQuestionResponse,
  SquadPassthroughResponse,
  TransferAccountLookupRequest,
  TransferInitiateRequest,
  Transaction,
  TransactionStats,
  VendorCreateResponse,
  Vendor,
  VendorCreate,
  VendorListItem,
  Verdict,
  Verification,
  Wallet,
  WalletCreateResponse,
  WalletTransaction,
} from "@/types";
import { getActiveVendorId } from "./session";

// Route all API calls through the Next.js proxy (app/api/[...proxy]/route.ts).
// This keeps the backend URL server-side only, eliminating HTTPS mixed-content errors
// when the frontend is served over HTTPS (e.g. Amplify) and the backend is a separate host.
// The proxy reads NEXT_PUBLIC_API_URL on the server and forwards the request.
const BASE = "";

type ApiErrorBody = {
  detail?: unknown;
  error?: string;
  message?: string;
  errors?: string[];
};

function errorMessage(body: ApiErrorBody, fallback = "Request failed"): string {
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    const messages = body.detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) return String((item as { msg?: unknown }).msg);
        return String(item);
      })
      .filter(Boolean);
    if (messages.length) return messages.join(", ");
  }
  if (body.detail && typeof body.detail === "object") {
    const detail = body.detail as { message?: string; errors?: string[] };
    if (Array.isArray(detail.errors) && detail.errors.length) {
      return `${detail.message || "Validation failed"}: ${detail.errors.join(", ")}`;
    }
    if (detail.message) return detail.message;
    return JSON.stringify(detail);
  }
  if (Array.isArray(body.errors) && body.errors.length) return body.errors.join(", ");
  if (body.error && body.detail) return `${body.error}: ${String(body.detail)}`;
  return body.error || body.message || fallback;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const activeVendorId = getActiveVendorId();
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(activeVendorId ? { "X-Vendor-Id": activeVendorId } : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = (await res.json().catch(() => ({ detail: "Request failed" }))) as ApiErrorBody;
    throw new Error(errorMessage(error, `HTTP ${res.status}`));
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

function withQuery(path: string, params?: Record<string, string | undefined>): string {
  const clean = Object.fromEntries(
    Object.entries(params || {}).filter((entry): entry is [string, string] => Boolean(entry[1])),
  );
  const qs = new URLSearchParams(clean).toString();
  return `${path}${qs ? `?${qs}` : ""}`;
}

function severityFromLegacy(value: unknown): Flag["severity"] {
  if (value === "critical" || value === "high" || value === "medium" || value === "low" || value === "info") {
    return value;
  }
  if (value === 3) return "high";
  if (value === 2) return "medium";
  if (value === 1) return "low";
  return "info";
}

function normalizeFlag(raw: Record<string, unknown>): Flag {
  const code = String(raw.flag_type || raw.code || raw.title || "verification_signal");
  return {
    flag_type: code.toLowerCase().replace(/\s+/g, "_"),
    severity: severityFromLegacy(raw.severity),
    detail: String(raw.detail || raw.description || "Verification signal requires review."),
    source_doc: String(raw.source_doc || raw.source || "verification"),
    evidence: String(raw.evidence || ""),
    check_method: String(raw.check_method || "backend_verification"),
    similarity_score: typeof raw.similarity_score === "number" ? raw.similarity_score : null,
  };
}

function notStartedVerification(vendorId: string, message?: string): Verification {
  return {
    vendor_id: vendorId,
    status: "not_started",
    trust_score: null,
    verdict: "pending",
    identity_score: 0,
    document_score: 0,
    business_score: 0,
    behaviour_score: 0,
    flags: [],
    completed_at: null,
    processing_time_ms: 0,
    ai_summary: message || "Verification has not been run yet for this vendor.",
    external_checks: [],
  };
}

function normalizeVerification(raw: Record<string, unknown>, vendorId: string): Verification {
  if (raw.status === "not_started") {
    return notStartedVerification(vendorId, String(raw.message || ""));
  }

  const score = typeof raw.trust_score === "number" ? raw.trust_score : 0;
  const flags = Array.isArray(raw.flags)
    ? raw.flags.map((flag) => normalizeFlag(flag as Record<string, unknown>))
    : [];

  return {
    id: String(raw.id || ""),
    vendor_id: String(raw.vendor_id || vendorId),
    status: String(raw.status || "completed"),
    trust_score: score,
    risk_level: typeof raw.risk_level === "string" ? raw.risk_level : undefined,
    verdict: (raw.verdict as Verification["verdict"]) || "pending",
    identity_score: typeof raw.identity_score === "number" ? raw.identity_score : score,
    document_score: typeof raw.document_score === "number" ? raw.document_score : Math.max(0, score - 4),
    business_score: typeof raw.business_score === "number" ? raw.business_score : Math.max(0, score - 10),
    behaviour_score: typeof raw.behaviour_score === "number" ? raw.behaviour_score : Math.max(0, score - 18),
    flags,
    completed_at: String(raw.completed_at || raw.created_at || "") || null,
    processing_time_ms: typeof raw.processing_time_ms === "number" ? raw.processing_time_ms : 0,
    ai_summary: String(raw.ai_summary || raw.summary || ""),
    external_checks: Array.isArray(raw.external_checks) ? (raw.external_checks as Verification["external_checks"]) : [],
  };
}

export const api = {
  createVendor: async (data: VendorCreate) => {
    const response = await request<VendorCreateResponse>("/api/vendors", {
      method: "POST",
      body: JSON.stringify(data),
    });
    return response.vendor;
  },

  loginVendor: (data: { business_name: string; rc_number: string }) =>
    request<Vendor>("/api/vendors/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getVendors: (params?: { status?: string; tier?: string }) =>
    request<VendorListItem[]>(withQuery("/api/v1/vendors/", params)),

  getVendor: (id: string) => request<VendorListItem>(`/api/v1/vendors/${id}`),

  getCurrentVendor: () => request<Vendor>("/api/vendors/me"),

  updateVendorStatus: (id: string, status: Verdict) =>
    request<Vendor>(`/api/v1/vendors/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  runVerification: async (vendorId: string, options?: { wait?: boolean }) => {
    const wait = options?.wait ?? true;
    const body = await request<{ verification?: Record<string, unknown> } & Record<string, unknown>>(
      `/api/v1/verify/${vendorId}${wait ? "" : "?wait=false"}`,
      { method: "POST" },
    );
    return normalizeVerification(body.verification || body, vendorId);
  },

  getVerification: async (vendorId: string) => {
    const res = await fetch(`${BASE}/api/v1/verify/${vendorId}`);
    if (res.status === 404) return notStartedVerification(vendorId);
    if (!res.ok) {
      const error = (await res.json().catch(() => ({ detail: "Request failed" }))) as ApiErrorBody;
      throw new Error(errorMessage(error, `HTTP ${res.status}`));
    }
    const body = (await res.json()) as Record<string, unknown>;
    return normalizeVerification(body, vendorId);
  },

  getFlags: (vendorId: string) => request<Flag[]>(`/api/v1/verify/${vendorId}/flags`),

  getWallet: async (): Promise<Wallet | null> => {
    try {
      return await request<Wallet>("/api/wallets/me");
    } catch (error) {
      if (error instanceof Error && error.message.toLowerCase().includes("wallet not found")) {
        return null;
      }
      throw error;
    }
  },

  getWalletTransactions: () => request<WalletTransaction[]>("/api/wallets/me/transactions"),

  createWallet: () => request<WalletCreateResponse>("/api/wallets", { method: "POST" }),

  getPaymentSecurityQuestion: () =>
    request<PaymentSecurityQuestionResponse>("/api/payments/security-question"),

  getPayments: (params?: { status?: string }) =>
    request<PaymentRecord[]>(withQuery("/api/payments", params)),

  getPaymentStatus: (transactionRef: string) =>
    request<PaymentLookupResponse>(`/api/payments/${encodeURIComponent(transactionRef)}`),

  getPaymentById: (transactionRef: string) =>
    request<PaymentLookupResponse>(`/api/payments/${encodeURIComponent(transactionRef)}`),

  initiatePayment: (payload: PaymentInitiateRequest) =>
    request<PaymentInitiateResponse>("/api/payments/initiate", {
      method: "POST",
      body: JSON.stringify({
        ...payload,
        currency: payload.currency || "NGN",
        payment_channels: payload.payment_channels || ["card", "bank_transfer", "ussd", "squad"],
        metadata: payload.metadata || {},
        pass_charge: payload.pass_charge ?? false,
      }),
    }),

  lookupTransferAccount: (payload: TransferAccountLookupRequest) =>
    request<SquadPassthroughResponse>("/api/transfers/account-lookup", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  initiateTransfer: (payload: TransferInitiateRequest) =>
    request<SquadPassthroughResponse>("/api/transfers", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  sendSquadWebhook: (payload: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/webhooks/squad", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  uploadDocument: async (vendorId: string, docType: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("doc_type", docType);

    const res = await fetch(`${BASE}/api/v1/documents/upload/${vendorId}`, {
      method: "POST",
      body: form,
    });

    if (!res.ok) {
      const error = (await res.json().catch(() => ({ detail: "Upload failed" }))) as ApiErrorBody;
      throw new Error(errorMessage(error, "Upload failed"));
    }
    return res.json();
  },

  getStats: () => request<DashboardStats>("/api/v1/dashboard/stats"),

  getQueue: () => request<VendorListItem[]>("/api/v1/dashboard/queue"),

  getTransactions: () => request<Transaction[]>("/api/v1/transactions/"),

  getTransactionStats: () => request<TransactionStats>("/api/v1/transactions/stats"),

  getAdminVendors: () => request<Vendor[]>("/api/v1/admin/vendors"),

  deleteAdminVendor: (id: string) =>
    request<void>(`/api/v1/admin/vendors/${id}`, {
      method: "DELETE",
    }),
};
