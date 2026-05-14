import type {
  DashboardStats,
  Flag,
  Transaction,
  TransactionStats,
  Vendor,
  VendorCreate,
  VendorListItem,
  Verdict,
  Verification,
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type ApiErrorBody = {
  detail?: unknown;
  error?: string;
  message?: string;
  errors?: string[];
};

function errorMessage(body: ApiErrorBody, fallback = "Request failed"): string {
  if (typeof body.detail === "string") return body.detail;
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
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
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
  createVendor: (data: VendorCreate) =>
    request<Vendor>("/api/v1/vendors/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getVendors: (params?: { status?: string; tier?: string }) =>
    request<VendorListItem[]>(withQuery("/api/v1/vendors/", params)),

  getVendor: (id: string) => request<VendorListItem>(`/api/v1/vendors/${id}`),

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
