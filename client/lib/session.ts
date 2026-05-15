"use client";

import { useSyncExternalStore } from "react";

const STORAGE_KEY = "trustgate.activeVendorId";

function readVendorId() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

function notify() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event("trustgate-active-vendor-changed"));
}

export function getActiveVendorId() {
  return readVendorId();
}

export function setActiveVendorId(vendorId: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, vendorId);
  notify();
}

export function clearActiveVendorId() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
  notify();
}

export function useActiveVendorId() {
  return useSyncExternalStore(
    (onStoreChange) => {
      window.addEventListener("storage", onStoreChange);
      window.addEventListener("trustgate-active-vendor-changed", onStoreChange);
      return () => {
        window.removeEventListener("storage", onStoreChange);
        window.removeEventListener("trustgate-active-vendor-changed", onStoreChange);
      };
    },
    readVendorId,
    () => null,
  );
}
