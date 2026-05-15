"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeftRight,
  Code2,
  LayoutDashboard,
  ShieldCheck,
  Settings,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

const primaryNav = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Vendors", href: "/dashboard/vendors", icon: Users },
  { label: "Transactions", href: "/dashboard/transactions", icon: ArrowLeftRight },
  { label: "Operations", href: "/dashboard/operations", icon: ShieldCheck },
];

const systemNav = [
  { label: "API Docs", href: "http://localhost:8000/docs", icon: Code2, external: true },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
];

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === "/dashboard";
  return pathname.startsWith(href);
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col bg-[linear-gradient(180deg,#0B3142_0%,#0D3D52_100%)] text-white lg:flex">
      <div className="flex h-16 items-center gap-3 border-b border-[#E5E9ED] bg-white px-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#E51E56] text-white">
          <ShieldCheck className="h-5 w-5" />
        </div>
        <div>
          <p className="text-[18px] font-bold leading-tight text-[#E51E56]">TrustGate</p>
          <p className="text-[11px] font-medium leading-tight text-[#4A6B7C]">Powered by Squad</p>
        </div>
      </div>

      <nav className="flex-1 px-4 py-6">
        <p className="px-3 text-[11px] font-semibold uppercase tracking-widest text-white/35">Menu</p>
        <div className="mt-3 space-y-1">
          {primaryNav.map((item) => {
            const active = isActive(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex h-10 items-center rounded-lg px-3 text-[13px] font-medium transition-colors",
                  active
                    ? "bg-white/10 text-white"
                    : "text-white/65 hover:bg-white/10 hover:text-white",
                )}
              >
                <Icon className="mr-2.5 h-[18px] w-[18px]" />
                {item.label}
              </Link>
            );
          })}
        </div>

        <p className="mt-8 px-3 text-[11px] font-semibold uppercase tracking-widest text-white/35">
          System
        </p>
        <div className="mt-3 space-y-1">
          {systemNav.map((item) => {
            const Icon = item.icon;
            const active = !item.external && isActive(pathname, item.href);
            const className = cn(
              "flex h-10 items-center rounded-lg px-3 text-[13px] font-medium transition-colors",
              active
                ? "bg-white/10 text-white"
                : "text-white/65 hover:bg-white/10 hover:text-white",
            );

            if (item.external) {
              return (
                <a
                  key={item.href}
                  className={className}
                  href={item.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Icon className="mr-2.5 h-[18px] w-[18px]" />
                  {item.label}
                </a>
              );
            }

            return (
              <Link key={item.href} href={item.href} className={className}>
                <Icon className="mr-2.5 h-[18px] w-[18px]" />
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="border-t border-white/10 p-4">
        <div className="flex items-center gap-3 rounded-lg bg-white/5 p-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#E51E56] text-[12px] font-semibold text-white">
            CO
          </div>
          <div>
            <p className="text-[13px] font-semibold leading-tight text-white">Compliance</p>
            <p className="text-[12px] leading-tight text-white/50">Officer</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
