"use client";

import useSWR from "swr";
import { api } from "./api";

export const useStats = () => useSWR("stats", api.getStats, { refreshInterval: 30000 });

export const useQueue = () => useSWR("queue", api.getQueue, { refreshInterval: 15000 });

export const useVendors = (filters?: { status?: string; tier?: string }) =>
  useSWR(["vendors", filters], () => api.getVendors(filters));

export const useVendor = (id: string) =>
  useSWR(id ? `vendor-${id}` : null, () => api.getVendor(id));

export const useVerification = (vendorId: string) =>
  useSWR(vendorId ? `verification-${vendorId}` : null, () => api.getVerification(vendorId));

export const useTransactions = () =>
  useSWR("transactions", api.getTransactions, { refreshInterval: 10000 });

export const useTransactionStats = () =>
  useSWR("transaction-stats", api.getTransactionStats, { refreshInterval: 10000 });
