"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";

const appRoutes = ["/dashboard", "/vendors", "/transactions", "/operations"];

function getDashboardLink(element: Element | null): HTMLAnchorElement | null {
  const anchor = element?.closest("a");
  if (!anchor) return null;
  if (anchor.target || anchor.hasAttribute("download")) return null;

  const href = anchor.getAttribute("href");
  if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) {
    return null;
  }

  const url = new URL(anchor.href, window.location.href);
  return url.origin === window.location.origin && appRoutes.some((route) => url.pathname === route || url.pathname.startsWith(`${route}/`)) ? anchor : null;
}

export function RouteLoadingIndicator() {
  const pathname = usePathname();
  const [pending, setPending] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }

      const anchor = getDashboardLink(event.target as Element | null);
      if (!anchor) return;

      const next = new URL(anchor.href);
      const current = `${window.location.pathname}${window.location.search}`;
      if (`${next.pathname}${next.search}` === current) return;

      setPending(true);
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
      timeoutRef.current = window.setTimeout(() => setPending(false), 4000);
    }

    document.addEventListener("click", handleClick, true);
    return () => {
      document.removeEventListener("click", handleClick, true);
      if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    };
  }, []);

  useEffect(() => {
    setPending(false);
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
  }, [pathname]);

  if (!pending) return null;

  return (
    <div className="fixed inset-x-0 top-0 z-50 h-1 bg-[#FDE8EE]" aria-live="polite" aria-label="Loading page">
      <div className="h-full w-1/3 animate-[route-progress_1s_ease-in-out_infinite] bg-[#E51E56]" />
    </div>
  );
}
