"use client";

import { MouseEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle, ChevronRight } from "lucide-react";
import { mutate } from "swr";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { useQueue } from "@/lib/hooks";
import { formatRelativeTime, getScoreBg, getScoreColor, getTierLabel, initials, vendorScore } from "@/lib/utils";
import type { VendorListItem, Verdict } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

function QueueSkeleton() {
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="h-5 w-32 rounded skeleton" />
        <div className="h-5 w-16 rounded-full skeleton" />
      </div>
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="flex gap-3 rounded-xl border border-[#E5E9ED] p-4">
          <div className="h-9 w-9 rounded-full skeleton" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-2/5 rounded skeleton" />
            <div className="h-3 w-3/5 rounded skeleton" />
            <div className="h-3 w-20 rounded skeleton" />
          </div>
        </div>
      ))}
    </Card>
  );
}

export function VendorQueue() {
  const router = useRouter();
  const { data, error, isLoading } = useQueue();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const vendors = data || [];

  async function updateStatus(event: MouseEvent<HTMLButtonElement>, vendor: VendorListItem, status: Verdict) {
    event.stopPropagation();
    const key = `${vendor.id}-${status}`;
    setActionLoading(key);
    const previous = data;
    await mutate(
      "queue",
      previous?.filter((item) => item.id !== vendor.id),
      false,
    );

    try {
      await api.updateVendorStatus(vendor.id, status);
        toast.success(
          status === "approved"
            ? "Vendor approved - Squad merchant account created"
            : "Vendor flagged - payment access disabled",
        );
      await mutate("queue");
      await mutate("stats");
    } catch (err) {
      await mutate("queue", previous, false);
      toast.error(err instanceof Error ? err.message : "Could not update vendor status");
    } finally {
      setActionLoading(null);
    }
  }

  if (isLoading) return <QueueSkeleton />;

  if (error) {
    return (
      <Card className="flex min-h-[350px] flex-col items-center justify-center text-center">
        <AlertCircle className="h-8 w-8 text-[#DC2626]" />
        <h3 className="mt-3 text-[15px] font-semibold text-[#0B3142]">Something went wrong</h3>
        <p className="mt-1 text-[13px] text-[#4A6B7C]">Failed to load review queue.</p>
        <Button
          className="mt-4"
          variant="secondary"
          loading={retrying}
          onClick={() => {
            setRetrying(true);
            void mutate("queue").finally(() => setRetrying(false));
          }}
        >
          Retry
        </Button>
      </Card>
    );
  }

  return (
    <Card className="min-h-[350px]">
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-[18px] font-semibold text-[#0B3142]">Needs Review</h3>
          <Badge variant="pending">{vendors.length}</Badge>
        </div>
        <Link
          href="/dashboard/vendors"
          className="inline-flex items-center gap-1 text-[13px] font-medium text-[#E51E56]"
        >
          View all <ChevronRight className="h-4 w-4" />
        </Link>
      </div>

      {vendors.length === 0 ? (
        <div className="flex min-h-[260px] flex-col items-center justify-center text-center">
          <CheckCircle className="h-9 w-9 text-[#0D9B68]" />
          <h4 className="mt-3 text-[15px] font-semibold text-[#0B3142]">No vendors pending review</h4>
          <p className="mt-1 text-[13px] text-[#4A6B7C]">All vendor decisions are currently up to date.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {vendors.slice(0, 6).map((vendor) => {
            const score = vendorScore(vendor);
            return (
              <button
                key={vendor.id}
                type="button"
                className="grid w-full grid-cols-[36px_1fr_auto] gap-3 rounded-xl border border-transparent p-3 text-left transition-colors hover:border-[#E5E9ED] hover:bg-[#F8F9FA]"
                onClick={() => router.push(`/dashboard/vendors/${vendor.id}`)}
              >
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#E8EEF2] text-[12px] font-semibold text-[#0B3142]">
                  {initials(vendor.business_name)}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-[14px] font-semibold text-[#0B3142]">
                    {vendor.business_name}
                  </span>
                  <span className="block truncate text-[12px] text-[#4A6B7C]">
                    {vendor.rc_number || "No RC"} · {vendor.city || "Nigeria"} · {getTierLabel(vendor.tier)}
                  </span>
                  <span className="mt-1 block text-[11px] text-[#8FA3AF]">
                    {formatRelativeTime(vendor.updated_at || vendor.created_at)}
                  </span>
                </span>
                <span className="flex flex-col items-end gap-2">
                  <span
                    className="rounded-full px-2.5 py-1 text-[12px] font-bold"
                    style={{ backgroundColor: getScoreBg(score), color: getScoreColor(score) }}
                  >
                    Score: {score}
                  </span>
                  <span className="flex gap-2">
                    <Button
                      size="sm"
                      variant="successOutline"
                      loading={actionLoading === `${vendor.id}-approved`}
                      onClick={(event) => void updateStatus(event, vendor, "approved")}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="dangerOutline"
                      loading={actionLoading === `${vendor.id}-flagged`}
                      onClick={(event) => void updateStatus(event, vendor, "flagged")}
                    >
                      Flag
                    </Button>
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      )}
    </Card>
  );
}
