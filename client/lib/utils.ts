import type { FlagSeverity, Tier, Vendor, VendorListItem, Verdict, Wallet } from "@/types";

export function formatNaira(kobo: number): string {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    minimumFractionDigits: 0,
  }).format(kobo / 100);
}

export function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("en-NG", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.max(1, Math.floor(diff / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function getScoreColor(score: number): string {
  if (score >= 70) return "#0D9B68";
  if (score >= 40) return "#D97706";
  return "#DC2626";
}

export function getScoreBg(score: number): string {
  if (score >= 70) return "#E6F7F1";
  if (score >= 40) return "#FEF3C7";
  return "#FEE2E2";
}

export function getVerdictLabel(verdict: string): string {
  const map: Record<string, string> = {
    approved: "Approved",
    review: "Under Review",
    flagged: "Flagged",
    blocked: "Flagged",
    pending: "Pending",
  };
  return map[verdict] || verdict;
}

export function getSeverityColor(severity: string): string {
  const map: Record<string, string> = {
    critical: "#DC2626",
    high: "#D97706",
    medium: "#0B3142",
    low: "#4A6B7C",
    info: "#8FA3AF",
  };
  return map[severity] || "#8FA3AF";
}

export function getTierLabel(tier: string): string {
  const map: Record<string, string> = {
    tier1: "Individual",
    tier2: "Small Business",
    tier3: "Company",
  };
  return map[tier] || tier;
}

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export function walletBankName(wallet?: Wallet | null, vendor?: Vendor | null): string {
  if (wallet?.bank) return wallet.bank;
  if (wallet?.bank_code === "058" || wallet?.bank_code === "000013") return "GTBank";
  if (vendor?.settlement_bank) return vendor.settlement_bank;
  if (vendor?.bank_name) return vendor.bank_name;
  if (wallet?.virtual_account_number) return "GTBank";
  return "No bank";
}

export function walletAccountName(wallet?: Wallet | null, vendor?: Vendor | null): string {
  return wallet?.account_name || vendor?.business_name || vendor?.settlement_account_name || vendor?.account_name || "No account name";
}

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function vendorScore(vendor: VendorListItem): number {
  if (typeof vendor.trust_score === "number") return vendor.trust_score;
  if (typeof vendor.verification_score === "number") return vendor.verification_score;
  const fallback: Record<Verdict, number> = {
    approved: 82,
    review: 52,
    flagged: 35,
    blocked: 19,
    pending: 41,
  };
  return fallback[vendor.status] ?? 50;
}

export function tierRequiredDocuments(tier: Tier): string[] {
  if (tier === "tier1") return ["directors_id"];
  if (tier === "tier2") return ["cac_certificate", "utility_bill", "directors_id"];
  return [
    "cac_certificate",
    "utility_bill",
    "directors_id",
    "cac_form_cac2",
    "cac_form_cac7",
    "memart",
  ];
}

export function documentLabel(docType: string): string {
  const labels: Record<string, string> = {
    directors_id: "Director's ID",
    cac_certificate: "CAC Certificate",
    utility_bill: "Utility Bill",
    cac_form_cac2: "CAC Form CAC2",
    cac_form_cac7: "CAC Form CAC7",
    memart: "MEMART",
    bank_statement: "Bank Statement",
    business_registration: "Business Registration",
  };
  return labels[docType] || docType;
}

export function severityWeight(severity: FlagSeverity): number {
  const order: Record<FlagSeverity, number> = {
    critical: 0,
    high: 1,
    medium: 2,
    low: 3,
    info: 4,
  };
  return order[severity];
}
