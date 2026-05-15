"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { ArrowRight, Copy, Eye, EyeOff, LogOut, RefreshCw } from "lucide-react";
import { mutate } from "swr";
import toast from "react-hot-toast";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { squadTransferBankOptions } from "@/lib/banks";
import { clearActiveVendorId, useActiveVendorId } from "@/lib/session";
import {
  useCurrentVendor,
  usePaymentSecurityQuestion,
  usePayments,
  useWallet,
  useWalletTransactions,
} from "@/lib/hooks";
import { walletAccountName, walletBankName } from "@/lib/utils";

function money(value?: number | null) {
  if (!value) return "NGN 0";
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(value / 100);
}

function responseData(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const nested = raw.squad_response;
  if (nested && typeof nested === "object") {
    const data = (nested as Record<string, unknown>).data;
    return data && typeof data === "object" ? (data as Record<string, unknown>) : null;
  }
  const data = raw.data;
  if (data && typeof data === "object" && !Array.isArray(data)) {
    return data as Record<string, unknown>;
  }
  return null;
}

export default function VendorPortalPage() {
  const router = useRouter();
  const activeVendorId = useActiveVendorId();
  const { data: vendor, error: vendorError } = useCurrentVendor(activeVendorId);
  const { data: wallet } = useWallet(activeVendorId);
  const { data: walletTransactions } = useWalletTransactions(activeVendorId);
  const { data: securityQuestion } = usePaymentSecurityQuestion(activeVendorId);
  const { data: payments } = usePayments(activeVendorId);

  const [paymentBusy, setPaymentBusy] = useState(false);
  const [paymentLookupBusy, setPaymentLookupBusy] = useState(false);
  const [transferLookupBusy, setTransferLookupBusy] = useState(false);
  const [transferBusy, setTransferBusy] = useState(false);
  const [showPaymentAnswer, setShowPaymentAnswer] = useState(false);
  const [showTransferAnswer, setShowTransferAnswer] = useState(false);
  const [paymentRef, setPaymentRef] = useState("");
  const [checkoutUrl, setCheckoutUrl] = useState("");
  const [lookupRef, setLookupRef] = useState("");
  const [lookupResult, setLookupResult] = useState<Record<string, unknown> | null>(null);
  const [transferLookup, setTransferLookup] = useState<Record<string, unknown> | null>(null);
  const [paymentForm, setPaymentForm] = useState({
    amount: "",
    customer_name: "",
    customer_email: "",
    security_answer: "",
  });
  const [transferForm, setTransferForm] = useState({
    bank_code: "",
    account_number: "",
    account_name: "",
    amount: "",
    remark: "",
    security_answer: "",
  });

  const transactions = useMemo(() => {
    if (Array.isArray(walletTransactions)) return walletTransactions;
    const data = responseData(walletTransactions);
    const rows = data?.rows;
    return Array.isArray(rows) ? rows : [];
  }, [walletTransactions]);
  const securityAnswerLabel = securityQuestion?.question || "Security question";

  function signOut() {
    clearActiveVendorId();
    router.push("/vendor/login");
  }

  async function initiatePayment() {
    setPaymentBusy(true);
    try {
      const response = await api.initiatePayment({
        amount: Number(paymentForm.amount),
        customer_name: paymentForm.customer_name,
        customer_email: paymentForm.customer_email,
        security_answer: paymentForm.security_answer,
        callback_url: `${window.location.origin}/vendor`,
      });
      setPaymentRef(response.transaction_ref);
      setLookupRef(response.transaction_ref);
      setCheckoutUrl(response.checkout_url || "");
      await mutate(["payments", activeVendorId, undefined]);
      toast.success("Payment link created");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not initiate payment");
    } finally {
      setPaymentBusy(false);
    }
  }

  async function lookupPayment() {
    if (!lookupRef.trim()) {
      toast.error("Enter a transaction reference");
      return;
    }
    setPaymentLookupBusy(true);
    try {
      const result = await api.getPaymentById(lookupRef.trim());
      setLookupResult(result as unknown as Record<string, unknown>);
      toast.success("Payment status refreshed");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Payment lookup failed");
    } finally {
      setPaymentLookupBusy(false);
    }
  }

  async function lookupTransferAccount() {
    if (!transferForm.bank_code) {
      toast.error("Select a bank");
      return;
    }
    if (!/^\d{10}$/.test(transferForm.account_number)) {
      toast.error("Enter a 10 digit account number");
      return;
    }
    setTransferLookupBusy(true);
    try {
      const result = await api.lookupTransferAccount({
        bank_code: transferForm.bank_code,
        account_number: transferForm.account_number,
      });
      setTransferLookup(result as unknown as Record<string, unknown>);
      const data = responseData(result);
      setTransferForm((current) => ({
        ...current,
        account_name: String(data?.account_name || data?.beneficiary_name || current.account_name),
      }));
      toast.success("Account confirmed");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Account lookup failed");
    } finally {
      setTransferLookupBusy(false);
    }
  }

  async function sendMoney() {
    if (!transferForm.bank_code) {
      toast.error("Select a bank");
      return;
    }
    if (!/^\d{10}$/.test(transferForm.account_number)) {
      toast.error("Enter a 10 digit account number");
      return;
    }
    if (!transferForm.account_name.trim()) {
      toast.error("Lookup the account before sending money");
      return;
    }
    setTransferBusy(true);
    try {
      await api.initiateTransfer({
        amount: Number(transferForm.amount),
        bank_code: transferForm.bank_code,
        account_number: transferForm.account_number,
        account_name: transferForm.account_name,
        remark: transferForm.remark.trim() || undefined,
        security_answer: transferForm.security_answer,
      });
      toast.success("Transfer submitted");
      await mutate(`wallet-transactions-${activeVendorId}`);
      setTransferForm((current) => ({ ...current, amount: "", remark: "", security_answer: "" }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Transfer failed");
    } finally {
      setTransferBusy(false);
    }
  }

  if (!activeVendorId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#F8F9FA] p-6">
        <Card className="w-full max-w-md text-center">
          <h1 className="text-[22px] font-bold text-[#0B3142]">Vendor sign in required</h1>
          <p className="mt-2 text-[13px] text-[#4A6B7C]">Use your business name and RC number to access your wallet.</p>
          <Button className="mt-5" onClick={() => router.push("/vendor/login")}>
            Go to Vendor Login
          </Button>
        </Card>
      </main>
    );
  }

  if (vendorError) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#F8F9FA] p-6">
        <Card className="w-full max-w-md text-center">
          <h1 className="text-[22px] font-bold text-[#0B3142]">Session unavailable</h1>
          <p className="mt-2 text-[13px] text-[#4A6B7C]">Sign in again to continue.</p>
          <Button className="mt-5" onClick={signOut}>
            Sign in again
          </Button>
        </Card>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#F8F9FA] px-5 py-8 lg:px-10">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex flex-col gap-4 rounded-xl border border-[#E5E9ED] bg-white p-5 card-shadow md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-[26px] font-bold text-[#0B3142]">{vendor?.business_name || "Vendor Portal"}</h1>
              <Badge variant={vendor?.status || "pending"}>{vendor?.status || "loading"}</Badge>
            </div>
            <p className="mt-1 text-[13px] text-[#4A6B7C]">
              {vendor?.rc_number || "No RC number"} · {securityQuestion?.question || "Security question unavailable"}
            </p>
          </div>
          <Button variant="secondary" leftIcon={<LogOut className="h-4 w-4" />} onClick={signOut}>
            Sign Out
          </Button>
        </div>

        <section className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-[16px] font-semibold text-[#0B3142]">Receive Money</h2>
                <p className="mt-1 text-[12px] text-[#4A6B7C]">
                  Share this wallet account to receive funds. Wallet creation is handled by the admin team.
                </p>
              </div>
              <Badge variant={wallet ? "success" : "pending"}>{wallet ? "Wallet active" : "Awaiting wallet"}</Badge>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-[#F8F9FA] p-4">
                <p className="text-[11px] uppercase tracking-wide text-[#8FA3AF]">Account number</p>
                <p className="mt-1 text-[22px] font-bold text-[#0B3142]">{wallet?.virtual_account_number || "Not assigned"}</p>
              </div>
              <div className="rounded-lg bg-[#F8F9FA] p-4">
                <p className="text-[11px] uppercase tracking-wide text-[#8FA3AF]">Bank</p>
                <p className="mt-1 text-[15px] font-semibold text-[#0B3142]">{walletBankName(wallet, vendor)}</p>
                <p className="mt-1 text-[12px] text-[#4A6B7C]">{walletAccountName(wallet, vendor)}</p>
              </div>
              <div className="rounded-lg bg-[#F8F9FA] p-4">
                <p className="text-[11px] uppercase tracking-wide text-[#8FA3AF]">Wallet status</p>
                <p className="mt-1 text-[15px] font-semibold text-[#0B3142]">{wallet?.status || "Not created"}</p>
                <Button
                  className="mt-3"
                  size="sm"
                  variant="secondary"
                  disabled={!wallet?.virtual_account_number}
                  leftIcon={<Copy className="h-3.5 w-3.5" />}
                  onClick={() => {
                    if (!wallet?.virtual_account_number) return;
                    void navigator.clipboard.writeText(wallet.virtual_account_number);
                    toast.success("Account number copied");
                  }}
                >
                  Copy
                </Button>
              </div>
            </div>
          </Card>

          <Card>
            <h2 className="text-[16px] font-semibold text-[#0B3142]">Recent Payments</h2>
            <p className="mt-1 text-[12px] text-[#4A6B7C]">{payments?.length || 0} payment records</p>
            <div className="mt-4 max-h-44 overflow-auto">
              {(payments || []).slice(0, 5).map((payment) => (
                <div key={payment.id || payment.transaction_ref} className="border-t border-[#E5E9ED] py-3 text-[12px]">
                  <p className="font-medium text-[#0B3142]">{payment.customer_name || payment.customer_email}</p>
                  <p className="text-[#4A6B7C]">{money(payment.amount)} · {payment.status}</p>
                </div>
              ))}
              {!payments?.length ? <p className="text-[12px] text-[#4A6B7C]">No payments yet.</p> : null}
            </div>
          </Card>
        </section>

        <section className="mt-4 grid gap-4 xl:grid-cols-2">
          <Card>
            <h2 className="text-[16px] font-semibold text-[#0B3142]">Initiate Payment</h2>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <Input label="Amount" inputMode="numeric" value={paymentForm.amount} onChange={(event) => setPaymentForm((current) => ({ ...current, amount: event.target.value }))} />
              <Input label="Customer Name" value={paymentForm.customer_name} onChange={(event) => setPaymentForm((current) => ({ ...current, customer_name: event.target.value }))} />
              <Input label="Customer Email" type="email" value={paymentForm.customer_email} onChange={(event) => setPaymentForm((current) => ({ ...current, customer_email: event.target.value }))} />
              <Input
                label={securityAnswerLabel}
                type={showPaymentAnswer ? "text" : "password"}
                value={paymentForm.security_answer}
                onChange={(event) => setPaymentForm((current) => ({ ...current, security_answer: event.target.value }))}
                rightElement={
                  <button type="button" className="flex h-7 w-7 items-center justify-center rounded-md text-[#4A6B7C]" onClick={() => setShowPaymentAnswer((current) => !current)}>
                    {showPaymentAnswer ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button loading={paymentBusy} onClick={() => void initiatePayment()}>
                Create Payment Link
              </Button>
              <Button variant="secondary" loading={paymentLookupBusy} onClick={() => void lookupPayment()}>
                Check Status
              </Button>
            </div>
            <div className="mt-4 rounded-lg bg-[#F8F9FA] p-4 text-[12px]">
              <p className="font-medium text-[#0B3142]">Latest transaction</p>
              <p className="mt-1 break-all text-[#4A6B7C]">{paymentRef || "None yet"}</p>
              {checkoutUrl ? (
                <a className="mt-2 block break-all text-[#E51E56] hover:underline" href={checkoutUrl} target="_blank" rel="noreferrer">
                  {checkoutUrl}
                </a>
              ) : null}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto]">
              <Input label="Transaction ref" value={lookupRef} onChange={(event) => setLookupRef(event.target.value)} />
              <Button className="sm:self-end" variant="secondary" loading={paymentLookupBusy} onClick={() => void lookupPayment()}>
                Lookup
              </Button>
            </div>
            {lookupResult ? (
              <pre className="mt-4 max-h-44 overflow-auto rounded-lg border border-[#E5E9ED] bg-white p-4 text-[12px] text-[#0B3142]">
                {JSON.stringify(lookupResult, null, 2)}
              </pre>
            ) : null}
          </Card>

          <Card>
            <h2 className="text-[16px] font-semibold text-[#0B3142]">Send Money</h2>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <Select
                label="Bank"
                options={squadTransferBankOptions}
                value={transferForm.bank_code}
                onChange={(event) => {
                  setTransferLookup(null);
                  setTransferForm((current) => ({ ...current, bank_code: event.target.value, account_name: "" }));
                }}
              />
              <Input
                label="Account Number"
                inputMode="numeric"
                maxLength={10}
                value={transferForm.account_number}
                onChange={(event) =>
                  {
                    setTransferLookup(null);
                    setTransferForm((current) => ({
                      ...current,
                      account_number: event.target.value.replace(/\D/g, "").slice(0, 10),
                      account_name: "",
                    }));
                  }
                }
              />
              <Input label="Amount" inputMode="numeric" value={transferForm.amount} onChange={(event) => setTransferForm((current) => ({ ...current, amount: event.target.value }))} />
              <Input className="sm:col-span-2" label="Remark (optional)" value={transferForm.remark} onChange={(event) => setTransferForm((current) => ({ ...current, remark: event.target.value }))} />
              <Input
                className="sm:col-span-2"
                label={securityAnswerLabel}
                type={showTransferAnswer ? "text" : "password"}
                value={transferForm.security_answer}
                onChange={(event) => setTransferForm((current) => ({ ...current, security_answer: event.target.value }))}
                rightElement={
                  <button type="button" className="flex h-7 w-7 items-center justify-center rounded-md text-[#4A6B7C]" onClick={() => setShowTransferAnswer((current) => !current)}>
                    {showTransferAnswer ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
              />
            </div>
            {transferForm.account_name ? (
              <div className="mt-4 rounded-lg border border-[#D7F0E6] bg-[#E6F7F1] p-4 text-[12px]">
                <p className="font-medium text-[#0B3142]">Verified account name</p>
                <p className="mt-1 text-[15px] font-semibold text-[#0D9B68]">{transferForm.account_name}</p>
              </div>
            ) : null}
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="secondary" loading={transferLookupBusy} onClick={() => void lookupTransferAccount()}>
                Lookup Account
              </Button>
              <Button
                loading={transferBusy}
                disabled={!transferForm.account_name || !transferLookup}
                leftIcon={<ArrowRight className="h-4 w-4" />}
                onClick={() => void sendMoney()}
              >
                Send Money
              </Button>
            </div>
            {transferLookup ? (
              <pre className="mt-4 max-h-44 overflow-auto rounded-lg border border-[#E5E9ED] bg-[#F8F9FA] p-4 text-[12px] text-[#0B3142]">
                {JSON.stringify(transferLookup, null, 2)}
              </pre>
            ) : null}
          </Card>
        </section>

        <Card className="mt-4">
          <div className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4 text-[#4A6B7C]" />
            <h2 className="text-[16px] font-semibold text-[#0B3142]">Wallet Activity</h2>
          </div>
          <div className="mt-4 max-h-72 overflow-auto rounded-lg border border-[#E5E9ED]">
            {transactions.length ? (
              <ul className="divide-y divide-[#E5E9ED] text-[12px]">
                {transactions.map((tx, index) => {
                  const item = tx as Record<string, unknown>;
                  const rawAmount = item.amount || item.principal_amount;
                  const amount =
                    typeof rawAmount === "number"
                      ? money(rawAmount)
                      : rawAmount
                        ? String(rawAmount)
                        : "Amount unavailable";
                  const direction = String(item.direction || "").toLowerCase();
                  const isDebit = direction === "debit";
                  const title = isDebit
                    ? `Transfer to ${String(item.account_name || item.account_number || "recipient")}`
                    : String(item.remarks || item.narration || item.transaction_reference || "Transaction");
                  return (
                    <li key={String(item.transaction_reference || item.reference || index)} className="px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-[#0B3142]">{title}</p>
                          <p className="text-[#4A6B7C]">{String(item.status || item.narration || "Submitted")}</p>
                        </div>
                        <p className={isDebit ? "font-semibold text-[#DC2626]" : "font-semibold text-[#0D9B68]"}>
                          {isDebit ? "-" : ""}
                          {amount}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="p-4 text-[12px] text-[#4A6B7C]">No wallet activity yet.</p>
            )}
          </div>
        </Card>
      </div>
    </main>
  );
}
