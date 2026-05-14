"use client";

import { motion } from "framer-motion";
import { getScoreColor } from "@/lib/utils";
import { Card } from "@/components/ui/Card";

interface ScoreBreakdownProps {
  identity: number;
  documents: number;
  business: number;
  behaviour: number;
  loading?: boolean;
}

export function ScoreBreakdown({
  behaviour,
  business,
  documents,
  identity,
  loading,
}: ScoreBreakdownProps) {
  const rows = [
    { label: "Identity", value: identity },
    { label: "Documents", value: documents },
    { label: "Business", value: business },
    { label: "Behaviour", value: behaviour },
  ];

  if (loading) {
    return (
      <Card className="space-y-5">
        <div className="h-5 w-40 rounded skeleton" />
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="grid grid-cols-[90px_1fr_32px] items-center gap-3">
            <div className="h-4 rounded skeleton" />
            <div className="h-2 rounded-full skeleton" />
            <div className="h-4 rounded skeleton" />
          </div>
        ))}
      </Card>
    );
  }

  return (
    <Card>
      <h3 className="mb-5 text-[18px] font-semibold text-[#0B3142]">Score Breakdown</h3>
      <div className="space-y-4">
        {rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[90px_1fr_34px] items-center gap-3">
            <span className="text-[13px] font-medium text-[#0B3142]">{row.label}</span>
            <span className="h-2 overflow-hidden rounded-full bg-[#E8EEF2]">
              <motion.span
                className="block h-full rounded-full"
                style={{ backgroundColor: getScoreColor(row.value) }}
                initial={{ width: 0 }}
                animate={{ width: `${row.value}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
              />
            </span>
            <span className="text-right text-[13px] font-semibold text-[#0B3142]">{row.value}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
