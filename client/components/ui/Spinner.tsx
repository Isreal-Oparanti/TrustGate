import { cn } from "@/lib/utils";

interface SpinnerProps {
  size?: "sm" | "md";
  className?: string;
}

export function Spinner({ size = "sm", className }: SpinnerProps) {
  const dimension = size === "sm" ? "h-4 w-4" : "h-5 w-5";

  return (
    <svg
      className={cn("animate-spin", dimension, className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z"
      />
    </svg>
  );
}
