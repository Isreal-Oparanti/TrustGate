"use client";

import useSWR from "swr";
import { api } from "./api";

export const useStats = () => useSWR("stats", api.getStats, { refreshInterval: 30000 });

export const useQueue = () => useSWR("queue", api.getQueue, { refreshInterval: 15000 });

export const useVendors = (filters?: { status?: string; tier?: string }) =>
  useSWR(["vendors", filters], () => api.getVendors(filters));

export const useVendor = (id: string) =>
  useSWR(id ? `vendor-${id}` : null, () => api.getVendor(id));

export const useCurrentVendor = (vendorId: string | null) =>
  useSWR(vendorId ? `vendor-me-${vendorId}` : null, api.getCurrentVendor);

export const useVerification = (vendorId: string) =>
  useSWR(vendorId ? `verification-${vendorId}` : null, () => api.getVerification(vendorId));

export const useTransactions = () =>
  useSWR("transactions", api.getTransactions, { refreshInterval: 10000 });

export const useTransactionStats = () =>
  useSWR("transaction-stats", api.getTransactionStats, { refreshInterval: 10000 });

export const useWallet = (vendorId: string | null) =>
  useSWR(vendorId ? `wallet-${vendorId}` : null, api.getWallet);

export const useWalletTransactions = (vendorId: string | null) =>
  useSWR(vendorId ? `wallet-transactions-${vendorId}` : null, api.getWalletTransactions);

export const usePaymentSecurityQuestion = (vendorId: string | null) =>
  useSWR(vendorId ? `payment-security-question-${vendorId}` : null, api.getPaymentSecurityQuestion);

export const usePayments = (vendorId: string | null, filters?: { status?: string }) =>
  useSWR(vendorId ? ["payments", vendorId, filters] : null, () => api.getPayments(filters));
