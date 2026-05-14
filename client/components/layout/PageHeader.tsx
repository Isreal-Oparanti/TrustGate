import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  breadcrumb?: ReactNode;
  action?: ReactNode;
}

export function PageHeader({ action, breadcrumb, subtitle, title }: PageHeaderProps) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {breadcrumb ? <div className="mb-3">{breadcrumb}</div> : null}
        <h2 className="text-[28px] font-bold leading-tight text-[#0B3142]">{title}</h2>
        {subtitle ? <p className="mt-1 text-[13px] text-[#4A6B7C]">{subtitle}</p> : null}
      </div>
      {action ? <div className="flex items-center gap-2">{action}</div> : null}
    </div>
  );
}
