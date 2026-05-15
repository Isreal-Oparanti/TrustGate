import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  helperText?: string;
  helperTone?: "default" | "danger";
  error?: string;
  rightElement?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, error, helperText, helperTone = "default", id, label, rightElement, ...props },
  ref,
) {
  const inputId = id || props.name;

  return (
    <label className="block" htmlFor={inputId}>
      <span className="mb-1.5 block text-[13px] font-medium leading-normal text-[#0B3142]">
        {label}
      </span>
      <span className="relative block">
        <input
          id={inputId}
          ref={ref}
          className={cn(
            "h-10 w-full rounded-lg border-[1.5px] border-[#E5E9ED] bg-white px-3 text-[14px] text-[#0B3142]",
            "placeholder:text-[#8FA3AF]",
            "focus:border-[#E51E56] focus:outline-none focus:ring-3 focus:ring-[rgba(229,30,86,0.12)]",
            error && "border-[#DC2626] focus:border-[#DC2626] focus:ring-[rgba(220,38,38,0.12)]",
            Boolean(rightElement) && "pr-10",
            className,
          )}
          aria-invalid={Boolean(error)}
          {...props}
        />
        {rightElement ? (
          <span className="absolute inset-y-0 right-2 flex items-center">{rightElement}</span>
        ) : null}
      </span>
      {error ? (
        <span className="mt-1 block text-[12px] leading-normal text-[#DC2626]">{error}</span>
      ) : helperText ? (
        <span className={`mt-1 block text-[12px] leading-normal ${helperTone === "danger" ? "text-[#DC2626]" : "text-[#4A6B7C]"}`}>
          {helperText}
        </span>
      ) : null}
    </label>
  );
});
