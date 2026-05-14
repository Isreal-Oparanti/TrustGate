"use client";

import { useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  Brain,
  CheckCircle,
  Clock,
  MapPin,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import { mutate } from "swr";
import toast from "react-hot-toast";
import { ScoreBreakdown } from "@/components/dashboard/ScoreBreakdown";
import { FlagList } from "@/components/vendors/FlagList";
import { VerificationStatus } from "@/components/vendors/VerificationStatus";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { api } from "@/lib/api";
import { useVendor, useVerification } from "@/lib/hooks";
import {
  formatDate,
  getTierLabel,
  getVerdictLabel,
  vendorScore,
} from "@/lib/utils";
import type { ExternalCheck, VendorListItem, Verdict } from "@/types";

function DetailSkeleton() {
  return (
    <div>
      <div className="mb-8 h-16 rounded-xl skeleton" />
      <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
        <Card className="flex min-h-[280px] flex-col items-center justify-center">
          <div className="h-32 w-32 rounded-full skeleton" />
          <div className="mt-5 h-6 w-24 rounded-full skeleton" />
        </Card>
        <div className="space-y-6">
          <Card className="space-y-5">
            <div className="h-5 w-40 rounded skeleton" />
            {Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="h-4 rounded skeleton" />
            ))}
          </Card>
          <Card>
            <div className="h-5 w-52 rounded skeleton" />
            <div className="mt-5 h-20 rounded skeleton" />
          </Card>
        </div>
      </div>
      <div className="mt-6 h-72 rounded-xl skeleton" />
    </div>
  );
}

function buildExternalChecks(vendor: VendorListItem, checks?: ExternalCheck[]): ExternalCheck[] {
  if (checks?.length) return checks;
  return [
    {
      id: "dojah-bvn",
      name: "BVN",
      status: vendor.bvn ? "confirmed" : "failed",
      detail: vendor.bvn ? "Verified" : "Missing BVN",
    },
    {
      id: "dojah-nin",
      name: "NIN",
      status: vendor.nin ? "confirmed" : "failed",
      detail: vendor.nin ? "Verified" : "Missing NIN",
    },
    {
      id: "cac-registry",
      name: "CAC Reg",
      status: vendor.rc_number ? "fallback" : "failed",
      detail: vendor.rc_number ? "Fallback" : "No RC number",
    },
    {
      id: "google-maps",
      name: "Google Maps",
      status: vendor.address ? "confirmed" : "failed",
      detail: vendor.address ? "Confirmed" : "Address unavailable",
    },
  ];
}

function ExternalChecks({ checks }: { checks: ExternalCheck[] }) {
  const [open, setOpen] = useState<string | null>(null);

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {checks.map((check) => {
        const Icon =
          check.status === "confirmed" ? CheckCircle : check.status === "fallback" ? TriangleAlert : XCircle;
        const color =
          check.status === "confirmed" ? "#0D9B68" : check.status === "fallback" ? "#D97706" : "#DC2626";

        return (
          <button
            key={check.id}
            type="button"
            className="rounded-xl border border-[#E5E9ED] bg-white p-4 text-left transition-colors hover:bg-[#F8F9FA]"
            onClick={() => setOpen((value) => (value === check.id ? null : check.id))}
          >
            <div className="flex items-center gap-2">
              <Icon className="h-4 w-4" style={{ color }} />
              <span className="text-[13px] font-semibold text-[#0B3142]">{check.name}</span>
            </div>
            <p className="mt-1 text-[12px] text-[#4A6B7C]">{check.detail}</p>
            {open === check.id ? (
              <pre className="mt-3 max-h-36 overflow-auto rounded-lg bg-[#F2F4F6] p-3 text-[11px] text-[#0B3142]">
                {JSON.stringify(check.raw || check, null, 2)}
              </pre>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

function VerificationNotStarted({
  onRunVerification,
  verifying,
}: {
  onRunVerification: () => void;
  verifying: boolean;
}) {
  return (
    <Card className="flex min-h-[360px] flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#E8EEF2]">
        <Clock className="h-8 w-8 text-[#4A6B7C]" />
      </div>
      <h3 className="mb-2 text-[15px] font-semibold text-[#0B3142]">Verification not yet run</h3>
      <p className="mb-6 max-w-xs text-[13px] text-[#4A6B7C]">
        Upload the required documents first, then trigger AI verification.
      </p>
      <Button variant="primary" onClick={onRunVerification} loading={verifying}>
        Run Verification Now
      </Button>
    </Card>
  );
}

export default function VendorDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const vendorId = params.id;
  const { data: vendor, error: vendorError, isLoading: vendorLoading } = useVendor(vendorId);
  const { data: verification, error: verificationError, isLoading: verificationLoading } =
    useVerification(vendor?.id || "");
  const [actionLoading, setActionLoading] = useState<Verdict | "verify" | null>(null);

  const verificationNotStarted = verification?.status === "not_started";
  const score = typeof verification?.trust_score === "number" ? verification.trust_score : vendor ? vendorScore(vendor) : 0;
  const summary =
    verification?.ai_summary ||
    "Vendor documents are internally consistent based on the latest available checks. External verification results should be reviewed alongside the signal list before a final compliance decision.";
  const checks = useMemo(
    () => (vendor ? buildExternalChecks(vendor, verification?.external_checks) : []),
    [vendor, verification?.external_checks],
  );

  async function updateStatus(status: Verdict) {
    if (!vendor) return;
    if (status === "blocked") {
      const confirmed = window.confirm(
        "Are you sure? This will prevent this vendor from receiving payments on Squad.",
      );
      if (!confirmed) return;
    }

    const previous = vendor;
    setActionLoading(status);
    await mutate(`vendor-${vendorId}`, { ...vendor, status }, false);

    try {
      await api.updateVendorStatus(vendorId, status);
      toast.success(
        status === "approved"
          ? "Vendor approved - Squad merchant account created"
          : status === "blocked"
            ? "Vendor blocked - payment access disabled"
            : "Vendor sent to review",
      );
      await mutate(`vendor-${vendorId}`);
      await mutate("queue");
      await mutate("stats");
    } catch (err) {
      await mutate(`vendor-${vendorId}`, previous, false);
      toast.error(err instanceof Error ? err.message : "Could not update vendor status");
    } finally {
      setActionLoading(null);
    }
  }

  async function pollVerificationResult() {
    const maxAttempts = 45;
    for (let attempts = 0; attempts < maxAttempts; attempts += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 4000));
      const result = await api.getVerification(vendorId);
      await mutate(`verification-${vendorId}`, result, false);
      if (result.verdict && result.verdict !== "pending" && result.status !== "not_started") {
        return result;
      }
    }
    throw new Error("Verification is taking longer than expected. You can check back later.");
  }

  async function runVerification() {
    setActionLoading("verify");
    const toastId = toast.loading("Running AI verification...");
    try {
      await api.runVerification(vendorId, { wait: false });
      const result = await pollVerificationResult();
      await mutate(`verification-${vendorId}`, result, false);
      await mutate(`vendor-${vendorId}`);
      toast.success("Verification complete", { id: toastId });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Verification failed. Please try again.", {
        id: toastId,
      });
    } finally {
      setActionLoading(null);
    }
  }

  if (vendorLoading) return <DetailSkeleton />;

  if (vendorError || !vendor) {
    return (
      <Card className="flex min-h-[420px] flex-col items-center justify-center text-center">
        <AlertCircle className="h-9 w-9 text-[#DC2626]" />
        <h2 className="mt-3 text-[18px] font-semibold text-[#0B3142]">Something went wrong</h2>
        <p className="mt-1 text-[13px] text-[#4A6B7C]">Failed to load vendor data. Try again.</p>
        <Button className="mt-4" variant="secondary" onClick={() => void mutate(`vendor-${vendorId}`)}>
          Retry
        </Button>
      </Card>
    );
  }

  return (
    <div className="pb-20 lg:pb-0">
      <div className="mb-8 flex flex-col gap-4 rounded-xl border border-[#E5E9ED] bg-white p-5 card-shadow lg:flex-row lg:items-center lg:justify-between">
        <div>
          <button
            type="button"
            className="mb-3 inline-flex items-center gap-2 text-[13px] font-medium text-[#4A6B7C] hover:text-[#0B3142]"
            onClick={() => router.back()}
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-[28px] font-bold leading-tight text-[#0B3142]">{vendor.business_name}</h2>
            <VerificationStatus status={vendor.status} />
          </div>
          <p className="mt-1 text-[13px] text-[#4A6B7C]">
            {vendor.rc_number || "No RC number"} · {getTierLabel(vendor.tier)} · {vendor.city || "Nigeria"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {vendor.status !== "approved" ? (
            <Button
              variant="success"
              loading={actionLoading === "approved"}
              leftIcon={<CheckCircle className="h-4 w-4" />}
              onClick={() => void updateStatus("approved")}
            >
              Approve
            </Button>
          ) : null}
          <Button
            variant="danger"
            loading={actionLoading === "blocked"}
            leftIcon={<XCircle className="h-4 w-4" />}
            onClick={() => void updateStatus("blocked")}
          >
            Block
          </Button>
        </div>
      </div>

      {verificationNotStarted ? (
        <VerificationNotStarted
          verifying={actionLoading === "verify"}
          onRunVerification={() => void runVerification()}
        />
      ) : (
      <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
        <Card className="flex flex-col items-center justify-center text-center">
          <ScoreRing score={score} size="lg" />
          <Badge className="mt-5 uppercase" variant={verification?.verdict || vendor.status}>
            {getVerdictLabel(verification?.verdict || vendor.status)}
          </Badge>
          <p className="mt-4 text-[12px] text-[#4A6B7C]">
            {verification?.completed_at ? `Completed ${formatDate(verification.completed_at)}` : "Awaiting latest verification"}
          </p>
        </Card>

        <div className="space-y-6">
          <ScoreBreakdown
            loading={verificationLoading && !verification}
            identity={verification?.identity_score ?? score}
            documents={verification?.document_score ?? Math.max(0, score - 4)}
            business={verification?.business_score ?? Math.max(0, score - 10)}
            behaviour={verification?.behaviour_score ?? Math.max(0, score - 18)}
          />

          <Card className="border-l-4 border-l-[#0B3142]">
            <div className="mb-3 flex items-center gap-2">
              <Brain className="h-5 w-5 text-[#0B3142]" />
              <h3 className="text-[18px] font-semibold text-[#0B3142]">AI Compliance Summary</h3>
            </div>
            <p className="text-[14px] italic leading-7 text-[#4A6B7C]">&quot;{summary}&quot;</p>
            {verificationError ? (
              <p className="mt-3 text-[12px] text-[#D97706]">
                Latest verification details are not available yet.
              </p>
            ) : null}
          </Card>
        </div>
      </div>
      )}

      {!verificationNotStarted ? (
        <section className="mt-6">
          <FlagList flags={verification?.flags || []} loading={verificationLoading && !verification} />
        </section>
      ) : null}

      <section className="mt-6">
        <div className="mb-3 flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-[#0B3142]" />
          <h3 className="text-[18px] font-semibold text-[#0B3142]">External Verification Results</h3>
        </div>
        <ExternalChecks checks={checks} />
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-3">
        <Card>
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-[#4A6B7C]" />
            <h3 className="text-[13px] font-semibold text-[#0B3142]">Registered Address</h3>
          </div>
          <p className="mt-2 text-[13px] text-[#4A6B7C]">{vendor.address}</p>
        </Card>
        <Card>
          <h3 className="text-[13px] font-semibold text-[#0B3142]">Contact</h3>
          <p className="mt-2 text-[13px] text-[#4A6B7C]">{vendor.email}</p>
          <p className="text-[13px] text-[#4A6B7C]">{vendor.phone}</p>
        </Card>
        <Card>
          <h3 className="text-[13px] font-semibold text-[#0B3142]">Squad Account</h3>
          <p className="mt-2 text-[13px] text-[#4A6B7C]">
            {vendor.squad_account_id || vendor.squad_merchant_id || "Not created yet"}
          </p>
        </Card>
      </section>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-[#E5E9ED] bg-white p-3 shadow-[0_-1px_3px_rgba(11,49,66,0.08)] lg:sticky lg:bottom-auto lg:top-20 lg:mt-6 lg:rounded-xl lg:border lg:p-4 lg:shadow-none">
        <div className="mx-auto flex max-w-6xl flex-wrap justify-end gap-2">
          <Button
            variant="secondary"
            loading={actionLoading === "verify"}
            leftIcon={<RefreshCw className="h-4 w-4" />}
            onClick={() => void runVerification()}
          >
            Run Verification Again
          </Button>
          {vendor.status !== "approved" ? (
            <Button
              variant="success"
              loading={actionLoading === "approved"}
              leftIcon={<CheckCircle className="h-4 w-4" />}
              onClick={() => void updateStatus("approved")}
            >
              Approve Vendor
            </Button>
          ) : null}
          <Button
            variant="warning"
            loading={actionLoading === "review"}
            leftIcon={<Clock className="h-4 w-4" />}
            onClick={() => void updateStatus("review")}
          >
            Send to Review
          </Button>
          <Button
            variant="danger"
            loading={actionLoading === "blocked"}
            leftIcon={<XCircle className="h-4 w-4" />}
            onClick={() => void updateStatus("blocked")}
          >
            Block Vendor
          </Button>
        </div>
      </div>
    </div>
  );
}
