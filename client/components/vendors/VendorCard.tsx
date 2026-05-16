"use client";

import { useRouter } from "next/navigation";
import { getScoreColor, getTierLabel, vendorScore } from "@/lib/utils";
import type { VendorListItem } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface VendorCardProps {
  vendor: VendorListItem;
}

export function VendorCard({ vendor }: VendorCardProps) {
  const router = useRouter();
  const score = vendorScore(vendor);

  return (
    <div className="grid grid-cols-1 gap-4 border-t border-[#E5E9ED] px-5 py-4 transition-colors hover:bg-[#F8F9FA] md:grid-cols-[2fr_1fr_1fr_1fr_auto] md:items-center">
      <div>
        <p className="text-[14px] font-semibold text-[#0B3142]">{vendor.business_name}</p>
        <p className="mt-1 text-[12px] text-[#4A6B7C]">
          {vendor.rc_number || "No RC"} · {vendor.city || "Nigeria"}
        </p>
      </div>
      <div>
        <p className="text-[13px] font-medium text-[#0B3142]">{getTierLabel(vendor.tier)}</p>
        <p className="text-[11px] text-[#8FA3AF]">{vendor.tier}</p>
      </div>
      <div className="max-w-[140px]">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-[13px] font-bold text-[#0B3142]">{score}</span>
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-[#E8EEF2]">
          <div className="h-full rounded-full" style={{ width: `${score}%`, backgroundColor: getScoreColor(score) }} />
        </div>
      </div>
      <div>
        <Badge variant={vendor.status}>{vendor.status === "review" ? "Review" : vendor.status}</Badge>
      </div>
      <Button variant="ghost" onClick={() => router.push(`/vendors/${vendor.id}`)}>
        View
      </Button>
    </div>
  );
}
