import { forwardRef, type SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface SelectOption {
  label: string;
  value: string;
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, error, id, label, options, ...props },
  ref,
) {
  const selectId = id || props.name;

  const control = (
    <span className="relative block">
      <select
        id={selectId}
        ref={ref}
        className={cn(
          "h-10 w-full appearance-none rounded-lg border-[1.5px] border-[#E5E9ED] bg-white px-3 pr-9 text-[14px] text-[#0B3142]",
          "focus:border-[#E51E56] focus:outline-none focus:ring-3 focus:ring-[rgba(229,30,86,0.12)]",
          error && "border-[#DC2626] focus:border-[#DC2626] focus:ring-[rgba(220,38,38,0.12)]",
          className,
        )}
        aria-invalid={Boolean(error)}
        {...props}
      >
        {options.map((option, index) => (
          <option key={`${option.value}-${option.label}-${index}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#4A6B7C]" />
    </span>
  );

  if (!label) return control;

  return (
    <label className="block" htmlFor={selectId}>
      <span className="mb-1.5 block text-[13px] font-medium leading-normal text-[#0B3142]">
        {label}
      </span>
      {control}
      {error ? (
        <span className="mt-1 block text-[12px] leading-normal text-[#DC2626]">{error}</span>
      ) : null}
    </label>
  );
});
