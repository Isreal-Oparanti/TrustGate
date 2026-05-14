"use client";

import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle } from "lucide-react";
import { formatNaira, formatRelativeTime } from "@/lib/utils";
import type { Transaction } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

interface TransactionRowProps {
  transaction: Transaction;
}

export function TransactionRow({ transaction }: TransactionRowProps) {
  const router = useRouter();

  return (
    <div
      className={`grid grid-cols-1 gap-3 border-l-4 px-5 py-4 md:grid-cols-[130px_1fr_1fr_80px_auto] md:items-center ${
        transaction.flagged ? "border-[#DC2626] bg-[#FFF8F8]" : "border-[#0D9B68] bg-white"
      }`}
    >
      <div>
        <p className="text-[15px] font-bold text-[#0B3142]">{formatNaira(transaction.amount)}</p>
        <p className="text-[12px] text-[#4A6B7C]">{transaction.transaction_ref}</p>
      </div>
      <div>
        <p className="text-[13px] font-semibold text-[#0B3142]">
          {transaction.business_name || transaction.merchant_id}
        </p>
        <p className="text-[12px] text-[#4A6B7C]">{transaction.rc_number || "RC pending"}</p>
      </div>
      <p className="truncate text-[13px] text-[#4A6B7C]">{transaction.customer_email}</p>
      <p className="text-[12px] text-[#8FA3AF]">{formatRelativeTime(transaction.created_at)}</p>
      <div className="flex items-center gap-2 md:justify-end">
        {transaction.flagged ? (
          <>
            <Badge variant="high">
              <AlertTriangle className="mr-1 h-3 w-3" />
              {transaction.flag_type || "Velocity spike"}
            </Badge>
            <Button size="sm" variant="secondary" onClick={() => router.push(`/dashboard/vendors/${transaction.merchant_id}`)}>
              Review
            </Button>
          </>
        ) : (
          <Badge variant="success">
            <CheckCircle className="mr-1 h-3 w-3" />
            Clean
          </Badge>
        )}
      </div>
    </div>
  );
}
