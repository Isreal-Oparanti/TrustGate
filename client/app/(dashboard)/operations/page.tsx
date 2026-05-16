"use client";

import { useEffect, useMemo, useState } from "react";
import { Copy, RefreshCw, Trash2, WalletCards } from "lucide-react";
import { mutate } from "swr";
import toast from "react-hot-toast";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { clearActiveVendorId, setActiveVendorId, useActiveVendorId } from "@/lib/session";
import { useCurrentVendor, useVendors, useWallet, useWalletTransactions } from "@/lib/hooks";
import { walletAccountName, walletBankName } from "@/lib/utils";

function responseData(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const nested = raw.squad_response;
  if (nested && typeof nested === "object") {
    const data = (nested as Record<string, unknown>).data;
    return data && typeof data === "object" ? (data as Record<string, unknown>) : null;
  }
  return null;
}

export default function OperationsPage() {
  const activeVendorId = useActiveVendorId();
  const [vendorInput, setVendorInput] = useState(activeVendorId || "");
  const [walletBusy, setWalletBusy] = useState(false);
  const { data: vendor } = useCurrentVendor(activeVendorId);
  const { data: wallet } = useWallet(activeVendorId);
  const { data: walletTransactions } = useWalletTransactions(activeVendorId);
  const { data: vendors, error: vendorsError, isLoading: vendorsLoading } = useVendors();

  const approvedVendors = useMemo(
    () => (vendors || []).filter((item) => item.status === "approved" && item.squad_account_id),
    [vendors],
  );
  const selectedVendor = useMemo(
    () => vendors?.find((item) => item.id === activeVendorId) || null,
    [activeVendorId, vendors],
  );
  const transactions = useMemo(() => {
    if (Array.isArray(walletTransactions)) return walletTransactions;
    const data = responseData(walletTransactions);
    const rows = data?.rows;
    return Array.isArray(rows) ? rows : [];
  }, [walletTransactions]);

  useEffect(() => {
    setVendorInput(activeVendorId || "");
  }, [activeVendorId]);

  function selectVendor(vendorId: string) {
    setVendorInput(vendorId);
    if (!vendorId) {
      clearActiveVendorId();
      toast.success("Vendor session cleared");
      return;
    }
    setActiveVendorId(vendorId);
    const picked = vendors?.find((item) => item.id === vendorId);
    toast.success(picked ? `${picked.business_name} selected` : "Vendor selected");
  }

  function saveVendorSession() {
    if (!vendorInput.trim()) {
      toast.error("Enter a vendor ID first");
      return;
    }
    setActiveVendorId(vendorInput.trim());
    toast.success("Vendor session saved");
  }

  async function createWallet() {
    if (!activeVendorId) {
      toast.error("Select a vendor first");
      return;
    }
    setWalletBusy(true);
    try {
      await api.createWallet();
      await mutate(`wallet-${activeVendorId}`);
      await mutate(`wallet-transactions-${activeVendorId}`);
      toast.success("Vendor wallet created");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Wallet creation failed");
    } finally {
      setWalletBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Operations"
        subtitle="Admin wallet setup for approved vendors. Vendors handle payments and transfers from the vendor portal."
      />

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <div className="flex flex-col gap-1">
            <h2 className="text-[16px] font-semibold text-[#0B3142]">Vendor session</h2>
            <p className="text-[12px] text-[#4A6B7C]">Choose the approved vendor that should receive a wallet.</p>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto]">
            <Select
              label="Vendor"
              value={activeVendorId || ""}
              disabled={vendorsLoading}
              onChange={(event) => selectVendor(event.target.value)}
              options={[
                {
                  label: vendorsLoading
                    ? "Loading vendors..."
                    : vendorsError
                      ? "Unable to load vendors"
                      : "Select a vendor",
                  value: "",
                },
                ...approvedVendors.map((item) => ({
                  label: `${item.business_name} - ${item.id}`,
                  value: item.id,
                })),
              ]}
            />
            <Button
              className="sm:self-end"
              variant="secondary"
              leftIcon={<Trash2 className="h-4 w-4" />}
              onClick={() => {
                clearActiveVendorId();
                setVendorInput("");
              }}
            >
              Clear
            </Button>
          </div>
          {vendorsError ? (
            <p className="mt-3 text-[12px] text-[#DC2626]">Vendor list could not be loaded. You can still paste an ID below.</p>
          ) : null}
          <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_auto]">
            <Input
              label="Vendor ID"
              value={vendorInput}
              onChange={(event) => setVendorInput(event.target.value)}
              placeholder="Paste a vendor id manually"
            />
            <Button className="sm:self-end" onClick={saveVendorSession}>
              Use ID
            </Button>
          </div>
          <div className="mt-4 grid gap-3 text-[13px] text-[#4A6B7C] sm:grid-cols-3">
            <div>
              <p className="text-[11px] uppercase tracking-wide">Current vendor</p>
              <p className="mt-1 break-all text-[#0B3142]">{selectedVendor?.business_name || vendor?.business_name || "Unavailable"}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wide">Status</p>
              <p className="mt-1 text-[#0B3142]">{selectedVendor?.status || vendor?.status || "Unavailable"}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wide">Squad ID</p>
              <p className="mt-1 break-all text-[#0B3142]">{selectedVendor?.squad_account_id || vendor?.squad_account_id || "Unavailable"}</p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-[16px] font-semibold text-[#0B3142]">Wallet setup</h2>
              <p className="mt-1 text-[12px] text-[#4A6B7C]">Create or inspect the selected vendor wallet.</p>
            </div>
            <Badge variant={wallet ? "success" : "pending"}>{wallet ? "Wallet active" : "Not created"}</Badge>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <Button loading={walletBusy} leftIcon={<WalletCards className="h-4 w-4" />} onClick={() => void createWallet()}>
              Create Wallet
            </Button>
            <Button
              variant="secondary"
              leftIcon={<RefreshCw className="h-4 w-4" />}
              onClick={() => {
                void mutate(`wallet-${activeVendorId}`);
                void mutate(`wallet-transactions-${activeVendorId}`);
              }}
            >
              Refresh
            </Button>
          </div>
          <div className="mt-4 grid gap-3 text-[13px] sm:grid-cols-2">
            <div className="rounded-lg bg-[#F8F9FA] p-4">
              <p className="text-[11px] uppercase tracking-wide text-[#8FA3AF]">Virtual account</p>
              <p className="mt-1 text-[#0B3142]">{wallet?.virtual_account_number || "Not assigned"}</p>
              <p className="mt-1 text-[#4A6B7C]">{walletBankName(wallet, selectedVendor || vendor)}</p>
            </div>
            <div className="rounded-lg bg-[#F8F9FA] p-4">
              <p className="text-[11px] uppercase tracking-wide text-[#8FA3AF]">Account name</p>
              <p className="mt-1 text-[#0B3142]">{walletAccountName(wallet, selectedVendor || vendor)}</p>
              <Button
                className="mt-3"
                size="sm"
                variant="secondary"
                disabled={!wallet?.customer_identifier}
                leftIcon={<Copy className="h-3.5 w-3.5" />}
                onClick={() => {
                  if (!wallet?.customer_identifier) return;
                  void navigator.clipboard.writeText(wallet.customer_identifier);
                  toast.success("Copied customer identifier");
                }}
              >
                Copy ID
              </Button>
            </div>
          </div>
        </Card>
      </section>

      <Card className="mt-4">
        <h2 className="text-[16px] font-semibold text-[#0B3142]">Wallet transactions</h2>
        <div className="mt-4 max-h-72 overflow-auto rounded-lg border border-[#E5E9ED]">
          {transactions.length ? (
            <ul className="divide-y divide-[#E5E9ED] text-[12px]">
              {transactions.map((tx, index) => {
                const item = tx as Record<string, unknown>;
                return (
                  <li key={String(item.transaction_reference || item.reference || index)} className="px-4 py-3">
                    <p className="font-medium text-[#0B3142]">{String(item.remarks || item.narration || item.transaction_reference || "Transaction")}</p>
                    <p className="text-[#4A6B7C]">{String(item.principal_amount || item.amount || "Amount unavailable")}</p>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="p-4 text-[12px] text-[#4A6B7C]">No wallet transactions yet.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
