"use client";

import { useMemo, useState } from "react";
import { getSeverityColor, severityWeight } from "@/lib/utils";
import type { Flag, FlagSeverity } from "@/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

interface FlagListProps {
  flags: Flag[];
  loading?: boolean;
}

const severityOrder: FlagSeverity[] = ["critical", "high", "medium", "low", "info"];

const signalLabels: Record<string, string> = {
  name_mismatch_critical: "Business name differs from documents",
  name_mismatch: "Business name variation found",
  address_mismatch: "Registered address differs from documents",
  partial_address_match: "Partial address match",
  rc_not_found: "RC number not found in documents",
  rc_mismatch: "RC number differs from document",
  cac_rc_document_mismatch: "CAC RC number differs from document",
  director_name_mismatch: "Director name mismatch",
  director_single_document_only: "Director appears in one document only",
  bvn_name_mismatch: "BVN name mismatch",
  bvn_nin_name_mismatch: "BVN and NIN names differ",
  no_web_presence: "No public web presence found",
  weak_web_presence: "Limited public web presence",
  weak_web_footprint: "Limited web footprint evidence",
  category_web_mismatch: "Business category conflicts with web results",
  address_not_found: "Address not found externally",
  address_low_precision: "Address match is approximate",
  ml_anomalous_outlier: "Unusual vendor profile pattern",
  inconsistent_online_presence: "Online presence needs review",
};

const sourceLabels: Record<string, string> = {
  nlp: "Document text analysis",
  identity: "Identity validation",
  agentic_verification: "External verification",
  anomaly_ml: "Behaviour model",
  anomaly: "Behaviour model",
  ocr: "Document extraction",
};

function humanize(value: string) {
  return value
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function signalLabel(flag: Flag) {
  return signalLabels[flag.flag_type.toLowerCase()] || humanize(flag.flag_type);
}

function sourceLabel(value: string) {
  return sourceLabels[value.toLowerCase()] || humanize(value);
}

export function FlagList({ flags, loading }: FlagListProps) {
  const [expanded, setExpanded] = useState(false);
  const sorted = useMemo(
    () => [...flags].sort((a, b) => severityWeight(a.severity) - severityWeight(b.severity)),
    [flags],
  );
  const visibleFlags = expanded ? sorted : sorted.slice(0, 10);
  const counts = severityOrder.map((severity) => ({
    severity,
    count: flags.filter((flag) => flag.severity === severity).length,
  }));

  if (loading) {
    return (
      <Card className="space-y-5">
        <div className="h-5 w-48 rounded skeleton" />
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="grid grid-cols-[10px_1fr] gap-3 border-t border-[#E5E9ED] pt-4">
            <div className="mt-1 h-2 w-2 rounded-full skeleton" />
            <div className="space-y-2">
              <div className="h-4 w-3/5 rounded skeleton" />
              <div className="h-3 w-4/5 rounded skeleton" />
              <div className="h-6 w-1/2 rounded skeleton" />
            </div>
          </div>
        ))}
      </Card>
    );
  }

  return (
    <Card>
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-[18px] font-semibold text-[#0B3142]">Verification Signals</h3>
          <p className="text-[12px] text-[#4A6B7C]">AI-detected document, identity, and behaviour signals.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {counts
            .filter((item) => item.count > 0)
            .map((item) => (
              <Badge key={item.severity} variant={item.severity}>
                {item.severity} {item.count}
              </Badge>
            ))}
        </div>
      </div>

      {visibleFlags.length === 0 ? (
        <p className="rounded-xl bg-[#F8F9FA] p-6 text-center text-[13px] text-[#4A6B7C]">
          No risk signals were found for this verification run.
        </p>
      ) : (
        <div className="divide-y divide-[#E5E9ED]">
          {visibleFlags.map((flag, index) => (
            <div key={`${flag.flag_type}-${index}`} className="grid grid-cols-[10px_1fr] gap-3 py-4 first:pt-0 last:pb-0">
              <span
                className="mt-1.5 h-2 w-2 rounded-full"
                style={{ backgroundColor: getSeverityColor(flag.severity) }}
              />
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] font-bold uppercase text-[#0B3142]">{flag.severity}</span>
                  <span className="text-[13px] font-semibold text-[#0B3142]">{signalLabel(flag)}</span>
                </div>
                <p className="mt-1 text-[13px] text-[#4A6B7C]">{flag.detail}</p>
                <p className="mt-2 text-[11px] text-[#8FA3AF]">
                  Source: {sourceLabel(flag.source_doc)} · check: {humanize(flag.check_method)}
                </p>
                {flag.evidence ? (
                  <p className="mt-2 inline-block rounded-md bg-[#F2F4F6] px-2 py-1 font-mono text-[12px] text-[#0B3142]">
                    {flag.evidence}
                  </p>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}

      {sorted.length > 10 ? (
        <Button className="mt-5" variant="ghost" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Show fewer" : `Show all ${sorted.length} signals`}
        </Button>
      ) : null}
    </Card>
  );
}
