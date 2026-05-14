"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Plus, Search, Users } from "lucide-react";
import { mutate } from "swr";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { VendorCard } from "@/components/vendors/VendorCard";
import { useVendors } from "@/lib/hooks";
import type { VendorListItem } from "@/types";

const pageSize = 10;

function withinDateFilter(vendor: VendorListItem, dateFilter: string) {
  if (dateFilter === "all") return true;
  const created = new Date(vendor.created_at).getTime();
  const now = Date.now();
  if (dateFilter === "today") {
    return new Date(vendor.created_at).toDateString() === new Date().toDateString();
  }
  if (dateFilter === "week") {
    return now - created <= 7 * 24 * 60 * 60 * 1000;
  }
  return true;
}

function VendorListSkeleton() {
  return (
    <Card padded={false} className="overflow-hidden">
      <div className="grid grid-cols-[2fr_1fr_1fr_1fr_auto] gap-4 px-5 py-4">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-3 rounded skeleton" />
        ))}
      </div>
      {Array.from({ length: 6 }).map((_, index) => (
        <div key={index} className="grid grid-cols-[2fr_1fr_1fr_1fr_auto] gap-4 border-t border-[#E5E9ED] px-5 py-5">
          <div className="space-y-2">
            <div className="h-4 w-44 rounded skeleton" />
            <div className="h-3 w-32 rounded skeleton" />
          </div>
          <div className="h-4 rounded skeleton" />
          <div className="h-4 rounded skeleton" />
          <div className="h-5 w-20 rounded-full skeleton" />
          <div className="h-8 w-16 rounded skeleton" />
        </div>
      ))}
    </Card>
  );
}

export default function VendorsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [tier, setTier] = useState("");
  const [status, setStatus] = useState("");
  const [dateFilter, setDateFilter] = useState("all");
  const [page, setPage] = useState(1);
  const { data, error, isLoading } = useVendors({
    tier: tier || undefined,
    status: status || undefined,
  });

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return (data || []).filter((vendor) => {
      const matchesSearch =
        !query ||
        vendor.business_name.toLowerCase().includes(query) ||
        (vendor.rc_number || "").toLowerCase().includes(query);
      return matchesSearch && withinDateFilter(vendor, dateFilter);
    });
  }, [data, dateFilter, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const visible = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const from = filtered.length === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const to = Math.min(currentPage * pageSize, filtered.length);

  return (
    <div>
      <PageHeader
        title="Vendors"
        subtitle="Search, review, and manage vendors moving through Squad verification."
        action={
          <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => router.push("/dashboard/vendors/new")}>
            Register New Vendor
          </Button>
        }
      />

      <Card className="mb-6">
        <div className="grid gap-3 md:grid-cols-[1fr_180px_180px_140px]">
          <Input
            label="Search"
            placeholder="Search by name or RC..."
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            rightElement={<Search className="h-4 w-4 text-[#8FA3AF]" />}
          />
          <Select
            label="Tier"
            value={tier}
            options={[
              { label: "All Tiers", value: "" },
              { label: "Individual", value: "tier1" },
              { label: "Small Business", value: "tier2" },
              { label: "Company", value: "tier3" },
            ]}
            onChange={(event) => {
              setTier(event.target.value);
              setPage(1);
            }}
          />
          <Select
            label="Status"
            value={status}
            options={[
              { label: "All Status", value: "" },
              { label: "Approved", value: "approved" },
              { label: "Under Review", value: "review" },
              { label: "Blocked", value: "blocked" },
              { label: "Pending", value: "pending" },
            ]}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          />
          <Select
            label="Created"
            value={dateFilter}
            options={[
              { label: "Today", value: "today" },
              { label: "Last 7 days", value: "week" },
              { label: "All time", value: "all" },
            ]}
            onChange={(event) => {
              setDateFilter(event.target.value);
              setPage(1);
            }}
          />
        </div>
      </Card>

      {isLoading ? (
        <VendorListSkeleton />
      ) : error ? (
        <Card className="flex min-h-[360px] flex-col items-center justify-center text-center">
          <AlertCircle className="h-9 w-9 text-[#DC2626]" />
          <h3 className="mt-3 text-[15px] font-semibold text-[#0B3142]">Something went wrong</h3>
          <p className="mt-1 text-[13px] text-[#4A6B7C]">Failed to load vendor data. Try again.</p>
          <Button className="mt-4" variant="secondary" onClick={() => void mutate(["vendors", { tier: tier || undefined, status: status || undefined }])}>
            Retry
          </Button>
        </Card>
      ) : filtered.length === 0 ? (
        <Card className="flex min-h-[360px] flex-col items-center justify-center text-center">
          <Users className="h-9 w-9 text-[#8FA3AF]" />
          <h3 className="mt-3 text-[15px] font-semibold text-[#0B3142]">No vendors yet</h3>
          <p className="mt-1 text-[13px] text-[#4A6B7C]">Register your first vendor to get started.</p>
          <Link href="/dashboard/vendors/new" className="mt-4">
            <Button>Register New Vendor</Button>
          </Link>
        </Card>
      ) : (
        <Card padded={false} className="overflow-hidden">
          <div className="hidden grid-cols-[2fr_1fr_1fr_1fr_auto] gap-4 bg-[#F8F9FA] px-5 py-3 text-[11px] font-bold uppercase tracking-wide text-[#8FA3AF] md:grid">
            <span>Business Name</span>
            <span>Tier</span>
            <span>Score</span>
            <span>Status</span>
            <span>Actions</span>
          </div>
          {visible.map((vendor) => (
            <VendorCard key={vendor.id} vendor={vendor} />
          ))}
          <div className="flex flex-col gap-3 border-t border-[#E5E9ED] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[12px] text-[#4A6B7C]">
              {from}-{to} of {filtered.length}
            </p>
            <div className="flex items-center gap-2">
              <Badge variant="pending">Page {currentPage}</Badge>
              <Button
                size="sm"
                variant="secondary"
                disabled={currentPage === 1}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                Prev
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={currentPage === totalPages}
                onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
