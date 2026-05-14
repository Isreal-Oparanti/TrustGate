"use client";

import Link from "next/link";
import { AlertCircle } from "lucide-react";
import { mutate } from "swr";
import { useQueue } from "@/lib/hooks";
import { formatRelativeTime } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const statusCopy = {
  approved: { label: "auto-approved", color: "#0D9B68" },
  blocked: { label: "blocked", color: "#DC2626" },
  review: { label: "sent to review", color: "#D97706" },
  pending: { label: "submitted", color: "#E51E56" },
};

function ActivitySkeleton() {
  return (
    <Card className="space-y-5">
      <div className="h-5 w-32 rounded skeleton" />
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="flex items-center gap-3">
          <div className="h-2.5 w-2.5 rounded-full skeleton" />
          <div className="h-4 flex-1 rounded skeleton" />
          <div className="h-3 w-10 rounded skeleton" />
        </div>
      ))}
    </Card>
  );
}

export function ActivityFeed() {
  const { data, error, isLoading } = useQueue();
  const vendors = [...(data || [])]
    .sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime())
    .slice(0, 10);

  if (isLoading) return <ActivitySkeleton />;

  if (error) {
    return (
      <Card className="flex min-h-[350px] flex-col items-center justify-center text-center">
        <AlertCircle className="h-8 w-8 text-[#DC2626]" />
        <h3 className="mt-3 text-[15px] font-semibold text-[#0B3142]">Something went wrong</h3>
        <p className="mt-1 text-[13px] text-[#4A6B7C]">Failed to load activity.</p>
        <Button className="mt-4" variant="secondary" onClick={() => void mutate("queue")}>
          Retry
        </Button>
      </Card>
    );
  }

  return (
    <Card className="min-h-[350px]">
      <h3 className="mb-5 text-[18px] font-semibold text-[#0B3142]">Recent Activity</h3>
      <div className="space-y-4">
        {vendors.length === 0 ? (
          <p className="text-[13px] text-[#4A6B7C]">No activity has been recorded yet.</p>
        ) : (
          vendors.map((vendor) => {
            const status = statusCopy[vendor.status];
            return (
              <Link
                key={vendor.id}
                href={`/dashboard/vendors/${vendor.id}`}
                className="grid grid-cols-[10px_1fr_auto] items-start gap-3 rounded-lg py-1"
              >
                <span className="mt-2 h-2.5 w-2.5 rounded-full" style={{ backgroundColor: status.color }} />
                <span className="text-[13px] leading-normal text-[#0B3142]">
                  Vendor <span className="font-semibold">"{vendor.business_name}"</span> {status.label}
                </span>
                <span className="text-right text-[11px] text-[#8FA3AF]">
                  {formatRelativeTime(vendor.updated_at || vendor.created_at)}
                </span>
              </Link>
            );
          })
        )}
      </div>
    </Card>
  );
}
