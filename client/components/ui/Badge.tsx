import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type BadgeVariant =
  | "approved"
  | "success"
  | "review"
  | "warning"
  | "blocked"
  | "danger"
  | "pending"
  | "info"
  | "critical"
  | "high"
  | "medium"
  | "low";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variants: Record<BadgeVariant, string> = {
  approved: "bg-[#E6F7F1] text-[#0D9B68]",
  success: "bg-[#E6F7F1] text-[#0D9B68]",
  review: "bg-[#FEF3C7] text-[#D97706]",
  warning: "bg-[#FEF3C7] text-[#D97706]",
  blocked: "bg-[#FEE2E2] text-[#DC2626]",
  danger: "bg-[#FEE2E2] text-[#DC2626]",
  pending: "bg-[#E8EEF2] text-[#0B3142]",
  info: "bg-[#E8EEF2] text-[#0B3142]",
  critical: "bg-[#FEE2E2] text-[#DC2626]",
  high: "bg-[#FEF3C7] text-[#D97706]",
  medium: "bg-[#E8EEF2] text-[#0B3142]",
  low: "bg-[#F2F4F6] text-[#4A6B7C]",
};

export function Badge({ children, className, variant = "pending" }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium leading-normal",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
