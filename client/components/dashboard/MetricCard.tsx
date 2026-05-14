"use client";

import { useEffect, useState, type ComponentType, type SVGProps } from "react";
import { animate, useMotionValue, useMotionValueEvent, useTransform } from "framer-motion";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/Card";

interface MetricCardProps {
  label: string;
  value: number;
  caption: string;
  trend?: string;
  color: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  loading?: boolean;
}

export function MetricCard({
  caption,
  color,
  icon: Icon,
  label,
  loading,
  trend,
  value,
}: MetricCardProps) {
  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (latest) => Math.round(latest));
  const [display, setDisplay] = useState(0);

  useMotionValueEvent(rounded, "change", (latest) => setDisplay(latest));

  useEffect(() => {
    const controls = animate(motionValue, value, { duration: 0.9, ease: "easeOut" });
    return controls.stop;
  }, [motionValue, value]);

  if (loading) {
    return (
      <Card>
        <div className="flex items-start justify-between">
          <div className="h-4 w-20 rounded skeleton" />
          <div className="h-9 w-9 rounded-full skeleton" />
        </div>
        <div className="mt-7 h-9 w-16 rounded skeleton" />
        <div className="mt-3 h-4 w-24 rounded skeleton" />
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-start justify-between">
        <p className="text-[13px] font-medium text-[#4A6B7C]">{label}</p>
        <div className="flex h-9 w-9 items-center justify-center rounded-full" style={{ backgroundColor: `${color}26` }}>
          <Icon className="h-5 w-5" style={{ color }} />
        </div>
      </div>
      <p className="mt-6 text-[36px] font-bold leading-none" style={{ color }}>
        {display.toLocaleString("en-NG")}
      </p>
      <div className="mt-2 flex items-center gap-2">
        <p className="text-[12px] text-[#4A6B7C]">{caption}</p>
        {trend ? (
          <span className={cn("text-[11px] font-medium", color === "#0D9B68" && "text-[#0D9B68]")}>
            {trend}
          </span>
        ) : null}
      </div>
    </Card>
  );
}
