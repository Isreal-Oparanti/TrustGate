"use client";

import { useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, ArrowLeftRight, RefreshCw } from "lucide-react";
import { mutate } from "swr";
import { PageHeader } from "@/components/layout/PageHeader";
import { TransactionRow } from "@/components/transactions/TransactionRow";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useTransactions, useTransactionStats } from "@/lib/hooks";
import { formatNaira } from "@/lib/utils";
import type { TransactionStats } from "@/types";

function FeedSkeleton() {
  return (
    <Card padded={false} className="overflow-hidden">
      {Array.from({ length: 7 }).map((_, index) => (
        <div key={index} className="grid grid-cols-[130px_1fr_1fr_80px_auto] gap-4 border-t border-[#E5E9ED] px-5 py-5 first:border-t-0">
          <div className="space-y-2">
            <div className="h-4 w-20 rounded skeleton" />
            <div className="h-3 w-14 rounded skeleton" />
          </div>
          <div className="space-y-2">
            <div className="h-4 w-40 rounded skeleton" />
            <div className="h-3 w-24 rounded skeleton" />
          </div>
          <div className="h-4 rounded skeleton" />
          <div className="h-4 rounded skeleton" />
          <div className="h-6 w-20 rounded-full skeleton" />
        </div>
      ))}
    </Card>
  );
}

function computeStats(transactions: Array<{
  amount: number;
  business_name?: string;
  merchant_id: string;
  flagged: boolean;
  transaction_status: string;
}>): TransactionStats {
  const merchantMap = new Map<string, number>();
  let total = 0;
  let suspended = 0;

  transactions.forEach((transaction) => {
    total += transaction.amount;
    if (transaction.transaction_status.toLowerCase().includes("suspend")) suspended += 1;
    const name = transaction.business_name || transaction.merchant_id;
    merchantMap.set(name, (merchantMap.get(name) || 0) + transaction.amount);
  });

  return {
    total_volume: total,
    transactions: transactions.length,
    flagged: transactions.filter((transaction) => transaction.flagged).length,
    suspended,
    top_merchants: [...merchantMap.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([name, volume]) => ({ name, volume })),
  };
}

function SummaryPanel({ stats }: { stats: TransactionStats }) {
  const flaggedRate = stats.transactions > 0 ? (stats.flagged / stats.transactions) * 100 : 0;

  return (
    <Card className="h-fit">
      <h3 className="text-[18px] font-semibold text-[#0B3142]">Today&apos;s Stats</h3>
      <div className="mt-5 space-y-4 border-t border-[#E5E9ED] pt-5">
        <div className="flex justify-between gap-3 text-[13px]">
          <span className="text-[#4A6B7C]">Total volume</span>
          <span className="font-semibold text-[#0B3142]">{formatNaira(stats.total_volume)}</span>
        </div>
        <div className="flex justify-between gap-3 text-[13px]">
          <span className="text-[#4A6B7C]">Transactions</span>
          <span className="font-semibold text-[#0B3142]">{stats.transactions}</span>
        </div>
        <div className="flex justify-between gap-3 text-[13px]">
          <span className="text-[#4A6B7C]">Flagged</span>
          <span className="font-semibold text-[#DC2626]">
            {stats.flagged} ({flaggedRate.toFixed(1)}%)
          </span>
        </div>
        <div className="flex justify-between gap-3 text-[13px]">
          <span className="text-[#4A6B7C]">Suspended</span>
          <span className="font-semibold text-[#0B3142]">{stats.suspended}</span>
        </div>
      </div>

      <h4 className="mt-8 border-t border-[#E5E9ED] pt-5 text-[13px] font-semibold uppercase tracking-wide text-[#8FA3AF]">
        Top Merchants
      </h4>
      <div className="mt-4 space-y-3">
        {stats.top_merchants.length === 0 ? (
          <p className="text-[13px] text-[#4A6B7C]">No volume recorded yet.</p>
        ) : (
          stats.top_merchants.map((merchant) => (
            <div key={merchant.name} className="flex justify-between gap-3 text-[13px]">
              <span className="truncate text-[#0B3142]">{merchant.name}</span>
              <span className="font-semibold text-[#0B3142]">{formatNaira(merchant.volume)}</span>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

export default function TransactionsPage() {
  const { data: transactions, error, isLoading } = useTransactions();
  const { data: serverStats } = useTransactionStats();
  const stats = useMemo(
    () => serverStats || computeStats(transactions || []),
    [serverStats, transactions],
  );

  return (
    <div>
      <PageHeader
        title="Transaction Monitoring"
        subtitle="Live payment behaviour and transaction fraud signals across onboarded merchants."
        action={
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-2 rounded-full bg-[#E6F7F1] px-3 py-1 text-[12px] font-medium text-[#0D9B68]">
              <span className="pulse-dot" />
              Live
            </span>
            <Button
              variant="secondary"
              leftIcon={<RefreshCw className="h-4 w-4" />}
              onClick={() => void mutate("transactions")}
            >
              Refresh
            </Button>
          </div>
        }
      />

      <div className="grid gap-6 xl:grid-cols-[1fr_280px]">
        <section>
          {isLoading ? (
            <FeedSkeleton />
          ) : error ? (
            <Card className="flex min-h-[420px] flex-col items-center justify-center text-center">
              <AlertCircle className="h-9 w-9 text-[#DC2626]" />
              <h3 className="mt-3 text-[15px] font-semibold text-[#0B3142]">Something went wrong</h3>
              <p className="mt-1 text-[13px] text-[#4A6B7C]">Failed to load transaction feed.</p>
              <Button className="mt-4" variant="secondary" onClick={() => void mutate("transactions")}>
                Retry
              </Button>
            </Card>
          ) : !transactions?.length ? (
            <Card className="flex min-h-[420px] flex-col items-center justify-center text-center">
              <ArrowLeftRight className="h-9 w-9 text-[#8FA3AF]" />
              <h3 className="mt-3 text-[15px] font-semibold text-[#0B3142]">No transactions yet</h3>
              <p className="mt-1 text-[13px] text-[#4A6B7C]">Live payment activity will appear here.</p>
            </Card>
          ) : (
            <Card padded={false} className="overflow-hidden">
              <AnimatePresence initial={false}>
                {transactions.map((transaction) => (
                  <motion.div
                    key={transaction.id}
                    layout
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 12 }}
                    transition={{ duration: 0.2 }}
                    className="border-t border-[#E5E9ED] first:border-t-0"
                  >
                    <TransactionRow transaction={transaction} />
                  </motion.div>
                ))}
              </AnimatePresence>
            </Card>
          )}
        </section>

        <SummaryPanel stats={stats} />
      </div>
    </div>
  );
}
