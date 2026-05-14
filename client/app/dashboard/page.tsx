"use client";

import { motion } from "framer-motion";
import { AlertCircle, CheckCircle, Clock, Users, XCircle } from "lucide-react";
import { mutate } from "swr";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { VendorQueue } from "@/components/dashboard/VendorQueue";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useStats } from "@/lib/hooks";

function StatsError() {
  return (
    <Card className="col-span-full flex min-h-[170px] flex-col items-center justify-center text-center">
      <AlertCircle className="h-8 w-8 text-[#DC2626]" />
      <h3 className="mt-3 text-[15px] font-semibold text-[#0B3142]">Something went wrong</h3>
      <p className="mt-1 text-[13px] text-[#4A6B7C]">Failed to load dashboard metrics.</p>
      <Button className="mt-4" variant="secondary" onClick={() => void mutate("stats")}>
        Retry
      </Button>
    </Card>
  );
}

function TrustDistribution({
  approved,
  blocked,
  pending,
  total,
}: {
  approved: number;
  blocked: number;
  pending: number;
  total: number;
}) {
  const denominator = Math.max(total, 1);
  const approvedPct = Math.round((approved / denominator) * 100);
  const pendingPct = Math.round((pending / denominator) * 100);
  const blockedPct = Math.max(0, 100 - approvedPct - pendingPct);

  return (
    <Card>
      <div className="mb-5 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-[18px] font-semibold text-[#0B3142]">Average Trust Score Summary</h3>
          <p className="text-[12px] text-[#4A6B7C]">Today&apos;s verification distribution by final verdict.</p>
        </div>
        <p className="text-[13px] font-medium text-[#0B3142]">{total.toLocaleString("en-NG")} vendors screened</p>
      </div>

      <div className="h-3 overflow-hidden rounded-full bg-[#E8EEF2]">
        <motion.div className="flex h-full" initial={{ width: 0 }} animate={{ width: "100%" }} transition={{ duration: 0.9, ease: "easeOut" }}>
          <div className="h-full bg-[#0D9B68]" style={{ width: `${approvedPct}%` }} />
          <div className="h-full bg-[#D97706]" style={{ width: `${pendingPct}%` }} />
          <div className="h-full bg-[#DC2626]" style={{ width: `${blockedPct}%` }} />
        </motion.div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-[12px] text-[#4A6B7C]">
        <span>
          <span className="mr-2 inline-block h-2 w-2 rounded-full bg-[#0D9B68]" />
          Approved ({approvedPct}%)
        </span>
        <span>
          <span className="mr-2 inline-block h-2 w-2 rounded-full bg-[#D97706]" />
          Reviewing ({pendingPct}%)
        </span>
        <span>
          <span className="mr-2 inline-block h-2 w-2 rounded-full bg-[#DC2626]" />
          Blocked ({blockedPct}%)
        </span>
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: stats, error, isLoading } = useStats();

  return (
    <div>
      <PageHeader
        title="Compliance Dashboard"
        subtitle="Live vendor verification, AI risk scoring, and Squad onboarding decisions."
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {error ? (
          <StatsError />
        ) : (
          <>
            <MetricCard
              caption="vendors"
              color="#0B3142"
              icon={Users}
              label="Today"
              loading={isLoading}
              value={stats?.total_today || 0}
            />
            <MetricCard
              caption="auto-appr"
              color="#0D9B68"
              icon={CheckCircle}
              label="Approved"
              loading={isLoading}
              trend="up 12% today"
              value={stats?.approved || 0}
            />
            <MetricCard
              caption="need review"
              color="#D97706"
              icon={Clock}
              label="Reviewing"
              loading={isLoading}
              value={stats?.pending_review || 0}
            />
            <MetricCard
              caption="auto-block"
              color="#DC2626"
              icon={XCircle}
              label="Blocked"
              loading={isLoading}
              value={stats?.blocked || 0}
            />
          </>
        )}
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(320px,2fr)]">
        <VendorQueue />
        <ActivityFeed />
      </section>

      <section className="mt-6">
        {isLoading ? (
          <Card>
            <div className="h-5 w-64 rounded skeleton" />
            <div className="mt-6 h-3 rounded-full skeleton" />
            <div className="mt-4 h-4 w-80 rounded skeleton" />
          </Card>
        ) : stats ? (
          <TrustDistribution
            approved={stats.approved}
            blocked={stats.blocked}
            pending={stats.pending_review}
            total={stats.total_today}
          />
        ) : null}
      </section>
    </div>
  );
}
