import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padded?: boolean;
}

export function Card({ children, className, padded = true, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "card-shadow rounded-xl border border-[#E5E9ED] bg-white",
        padded && "p-6",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
