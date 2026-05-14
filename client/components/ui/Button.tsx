import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Spinner } from "./Spinner";

type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "success"
  | "warning"
  | "danger"
  | "successOutline"
  | "dangerOutline";

type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-[#E51E56] text-white hover:bg-[#C4174A] active:scale-[0.98] disabled:hover:bg-[#E51E56]",
  secondary:
    "border border-[#0B3142] bg-transparent text-[#0B3142] hover:bg-[#E8EEF2] active:scale-[0.98]",
  ghost: "bg-transparent text-[#4A6B7C] hover:bg-[#F2F4F6] active:scale-[0.98]",
  success: "bg-[#0D9B68] text-white hover:bg-[#0b8359] active:scale-[0.98]",
  warning: "bg-[#D97706] text-white hover:bg-[#b86105] active:scale-[0.98]",
  danger: "bg-[#DC2626] text-white hover:bg-[#b91c1c] active:scale-[0.98]",
  successOutline:
    "border border-[#0D9B68] bg-transparent text-[#0D9B68] hover:bg-[#E6F7F1] active:scale-[0.98]",
  dangerOutline:
    "border border-[#DC2626] bg-transparent text-[#DC2626] hover:bg-[#FEE2E2] active:scale-[0.98]",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[11px]",
  md: "h-9 px-4 text-[13px]",
  lg: "h-11 px-6 text-[14px]",
};

export function Button({
  children,
  className,
  disabled,
  leftIcon,
  loading,
  rightIcon,
  size = "md",
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150",
        "focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-[rgba(229,30,86,0.18)]",
        "disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {loading ? <Spinner size={size === "lg" ? "md" : "sm"} /> : leftIcon}
      {children}
      {!loading ? rightIcon : null}
    </button>
  );
}
