export type Tier = "tier1" | "tier2" | "tier3";
export type Verdict = "approved" | "review" | "blocked" | "pending";
export type FlagSeverity = "critical" | "high" | "medium" | "low" | "info";

export interface FormState {
  business_name: string;
  tier: Tier;
  rc_number: string;
  director_name: string;
  business_category: string;
  website_url: string;
  social_media_url: string;
  expected_monthly_volume: string;
  bvn: string;
  nin: string;
  email: string;
  phone: string;
  address: string;
  bank_name: string;
  bank_code: string;
  account_number: string;
  account_name: string;
}

export interface Vendor {
  id: string;
  business_name: string;
  rc_number: string | null;
  director_name?: string | null;
  business_category?: string | null;
  website_url?: string | null;
  social_media_url?: string | null;
  expected_monthly_volume?: number | null;
  bank_name?: string | null;
  bank_code?: string | null;
  account_number?: string | null;
  account_name?: string | null;
  bvn: string;
  nin: string;
  email: string;
  phone: string;
  address: string;
  tier: Tier;
  status: Verdict;
  squad_account_id: string | null;
  squad_merchant_id?: string | null;
  created_at: string;
}

export interface VendorCreate {
  business_name: string;
  rc_number?: string | null;
  director_name?: string;
  business_category?: string;
  website_url?: string;
  social_media_url?: string;
  expected_monthly_volume?: number;
  bank_name?: string;
  bank_code?: string;
  account_number?: string;
  account_name?: string;
  bvn: string;
  nin: string;
  email: string;
  phone: string;
  address: string;
  tier: Tier;
}

export interface VendorListItem extends Vendor {
  trust_score?: number;
  verification_score?: number;
  city?: string;
  updated_at?: string;
}

export interface Flag {
  flag_type: string;
  severity: FlagSeverity;
  detail: string;
  source_doc: string;
  evidence: string;
  check_method: string;
  similarity_score: number | null;
}

export interface Verification {
  id?: string;
  vendor_id: string;
  status?: "not_started" | "completed" | string;
  trust_score: number | null;
  verdict: Verdict;
  risk_level?: string;
  identity_score: number;
  document_score: number;
  business_score: number;
  behaviour_score: number;
  flags: Flag[];
  completed_at: string | null;
  processing_time_ms: number;
  ai_summary?: string;
  external_checks?: ExternalCheck[];
}

export interface ExternalCheck {
  id: string;
  name: string;
  status: "confirmed" | "fallback" | "failed";
  detail: string;
  raw?: Record<string, unknown>;
}

export interface DashboardStats {
  total_today: number;
  approved: number;
  pending_review: number;
  blocked: number;
  avg_score: number;
}

export interface Transaction {
  id: string;
  merchant_id: string;
  transaction_ref: string;
  amount: number;
  customer_email: string;
  transaction_status: string;
  flagged: boolean;
  created_at: string;
  business_name?: string;
  rc_number?: string | null;
  flag_type?: string;
}

export interface TransactionStats {
  total_volume: number;
  transactions: number;
  flagged: number;
  suspended: number;
  top_merchants: Array<{
    name: string;
    volume: number;
  }>;
}
