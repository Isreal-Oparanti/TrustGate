"use client";

import { useMemo } from "react";
import { usePathname } from "next/navigation";
import { Bell, RefreshCw } from "lucide-react";
import { mutate } from "swr";
import { Button } from "@/components/ui/Button";

function titleFromPath(pathname: string): string {
  if (pathname.includes("/transactions")) return "Transaction Monitoring";
  if (pathname.includes("/vendors/new")) return "Register Vendor";
  if (pathname.includes("/vendors/")) return "Vendor Review";
  if (pathname.includes("/vendors")) return "Vendors";
  return "Dashboard";
}

export function Topbar() {
  const pathname = usePathname();
  const title = useMemo(() => titleFromPath(pathname), [pathname]);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-l border-[#E5E9ED] bg-white px-5 lg:ml-60 lg:px-8">
      <div>
        <h1 className="text-[18px] font-semibold leading-tight text-[#0B3142]">{title}</h1>
      </div>

      <div className="flex items-center gap-3">
        <Button
          aria-label="Refresh dashboard data"
          className="h-9 w-9 px-0"
          variant="ghost"
          onClick={() => void mutate(() => true)}
        >
          <RefreshCw className="h-4 w-4" />
        </Button>
        <button
          type="button"
          className="relative flex h-9 w-9 items-center justify-center rounded-lg text-[#4A6B7C] transition-colors hover:bg-[#F2F4F6]"
          aria-label="Notifications"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#E51E56] px-1 text-[10px] font-semibold leading-none text-white">
            3
          </span>
        </button>
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#E51E56] text-[12px] font-semibold text-white">
          CO
        </div>
      </div>
    </header>
  );
}
