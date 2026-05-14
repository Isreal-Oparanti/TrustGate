import { CheckCircle, Clock, XCircle } from "lucide-react";
import type { Verdict } from "@/types";
import { getVerdictLabel } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";

interface VerificationStatusProps {
  status: Verdict;
}

export function VerificationStatus({ status }: VerificationStatusProps) {
  const Icon = status === "approved" ? CheckCircle : status === "blocked" ? XCircle : Clock;

  return (
    <div className="flex items-center gap-2">
      <Icon className="h-4 w-4 text-[#4A6B7C]" />
      <Badge variant={status}>{getVerdictLabel(status)}</Badge>
    </div>
  );
}
