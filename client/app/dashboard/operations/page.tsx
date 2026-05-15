"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ArrowRight, Copy, Eye, EyeOff, RefreshCw, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { PageHeader } from "@/components/layout/PageHeader";
import { api } from "@/lib/api";
import {
  clearActiveVendorId,
  setActiveVendorId,
  useActiveVendorId,
} from "@/lib/session";
import {
  useCurrentVendor,
  usePayments,
  usePaymentSecurityQuestion,
  useVendors,
  useWallet,
  useWalletTransactions,
} from "@/lib/hooks";

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <div className="flex flex-col gap-1">
        <h2 className="text-[16px] font-semibold text-[#0B3142]">{title}</h2>
        <p className="text-[12px] text-[#4A6B7C]">{description}</p>
      </div>
      <div className="mt-5">{children}</div>
    </Card>
  );
}

export default function OperationsPage() {
  const activeVendorId = useActiveVendorId();
  const [vendorInput, setVendorInput] = useState(activeVendorId || "");
  const [paymentForm, setPaymentForm] = useState({
    amount: "",
    customer_email: "",
    customer_name: "",
    security_answer: "",
    callback_url: "",
  });
  const [paymentRef, setPaymentRef] = useState("");
  const [paymentCheckoutUrl, setPaymentCheckoutUrl] = useState("");
  const [lookupRef, setLookupRef] = useState("");
  const [lookupResult, setLookupResult] = useState<Record<string, unknown> | null>(null);
  const [walletBusy, setWalletBusy] = useState(false);
  const [paymentBusy, setPaymentBusy] = useState(false);
  const [paymentLookupBusy, setPaymentLookupBusy] = useState(false);
  const [showPaymentSecurityAnswer, setShowPaymentSecurityAnswer] = useState(false);
  const [showTransferSecurityAnswer, setShowTransferSecurityAnswer] = useState(false);
  const [transferForm, setTransferForm] = useState({
    bank_code: "",
    account_number: "",
    amount: "",
    account_name: "",
    remark: "",
    security_answer: "",
  });
  const [transferLookup, setTransferLookup] = useState<Record<string, unknown> | null>(null);
  const [transferLookupBusy, setTransferLookupBusy] = useState(false);
  const [transferBusy, setTransferBusy] = useState(false);
  const [webhookBusy, setWebhookBusy] = useState(false);
  const [status, setStatus] = useState<{ kind: "success" | "error" | "info"; message: string } | null>(null);

  const { data: vendor } = useCurrentVendor(activeVendorId);
  const { data: wallet } = useWallet(activeVendorId);
  const { data: walletTransactions } = useWalletTransactions(activeVendorId);
  const { data: securityQuestion } = usePaymentSecurityQuestion(activeVendorId);
  const { data: payments } = usePayments(activeVendorId);
  const { data: vendors, error: vendorsError, isLoading: vendorsLoading } = useVendors();
  const approvedVendors = useMemo(
    () => (vendors || []).filter((item) => item.status === "approved" && item.squad_account_id),
    [vendors],
  );
  const selectedVendor = useMemo(
    () => vendors?.find((item) => item.id === activeVendorId) || null,
    [activeVendorId, vendors],
  );

  const paymentQuestion = useMemo(
    () => securityQuestion?.question || "This vendor has no payment security question yet.",
    [securityQuestion?.question],
  );

  useEffect(() => {
    setVendorInput(activeVendorId || "");
  }, [activeVendorId]);

  async function saveVendorSession() {
    if (!vendorInput.trim()) {
      toast.error("Enter a vendor ID first");
      setStatus({ kind: "error", message: "Vendor session not saved." });
      return;
    }
    setActiveVendorId(vendorInput.trim());
    toast.success("Vendor session saved");
    setStatus({ kind: "success", message: "Active vendor session updated." });
  }

  function selectVendor(vendorId: string) {
    setVendorInput(vendorId);
    if (!vendorId) {
      clearActiveVendorId();
      toast.success("Vendor session cleared");
      setStatus({ kind: "info", message: "No active vendor selected." });
      return;
    }
    setActiveVendorId(vendorId);
    const picked = vendors?.find((item) => item.id === vendorId);
    toast.success(picked ? `${picked.business_name} selected` : "Vendor selected");
    setStatus({
      kind: "success",
      message: picked
        ? `Active vendor set to ${picked.business_name}. Payments and transfers will use this vendor.`
        : "Active vendor session updated.",
    });
  }

  async function createWallet() {
    if (!activeVendorId) {
      toast.error("Set an active vendor first");
      setStatus({ kind: "error", message: "Wallet creation needs an active vendor." });
      return;
    }
    setWalletBusy(true);
    try {
      await api.createWallet();
      toast.success("Wallet created");
      setStatus({ kind: "success", message: "Wallet created successfully." });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Wallet creation failed");
      setStatus({ kind: "error", message: error instanceof Error ? error.message : "Wallet creation failed." });
    } finally {
      setWalletBusy(false);
    }
  }

  async function submitPayment() {
    if (!activeVendorId) {
      toast.error("Set an active vendor first");
      setStatus({ kind: "error", message: "Payment initiation needs an active vendor." });
      return;
    }
    setPaymentBusy(true);
    try {
      const response = await api.initiatePayment({
        amount: Number(paymentForm.amount),
        customer_email: paymentForm.customer_email,
        customer_name: paymentForm.customer_name,
        security_answer: paymentForm.security_answer,
        callback_url: paymentForm.callback_url || null,
      });
      setPaymentRef(response.transaction_ref);
      setPaymentCheckoutUrl(response.checkout_url || "");
      setLookupRef(response.transaction_ref);
      toast.success(response.checkout_url ? "Payment link ready" : "Payment initiated");
      setStatus({
        kind: "success",
        message: response.checkout_url
          ? "Payment initiated successfully. Share or open the checkout link below."
          : "Payment initiated successfully, but no checkout URL was returned.",
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Payment initiation failed");
      setStatus({ kind: "error", message: error instanceof Error ? error.message : "Payment initiation failed." });
    } finally {
      setPaymentBusy(false);
    }
  }

  async function lookupPayment() {
    if (!lookupRef.trim()) {
      toast.error("Enter a transaction reference");
      setStatus({ kind: "error", message: "Payment lookup needs a transaction reference." });
      return;
    }
    setPaymentLookupBusy(true);
    try {
      const response = await api.getPaymentById(lookupRef.trim());
      setLookupResult(response as unknown as Record<string, unknown>);
      setStatus({ kind: "success", message: "Payment lookup completed." });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Lookup failed");
      setStatus({ kind: "error", message: error instanceof Error ? error.message : "Payment lookup failed." });
    } finally {
      setPaymentLookupBusy(false);
    }
  }

  async function lookupTransferAccount() {
    if (!transferForm.bank_code || !transferForm.account_number) {
      toast.error("Enter bank code and account number");
      setStatus({ kind: "error", message: "Transfer lookup needs bank code and account number." });
      return;
    }
    setTransferLookupBusy(true);
    try {
      const response = await api.lookupTransferAccount({
        bank_code: transferForm.bank_code,
        account_number: transferForm.account_number,
      });
      setTransferLookup(response as unknown as Record<string, unknown>);
      const raw = response as unknown as Record<string, unknown>;
      const data = (raw.squad_response as Record<string, unknown> | undefined)?.data as
        | Record<string, unknown>
        | undefined;
      setTransferForm((current) => ({
        ...current,
        account_name:
          String(data?.account_name || data?.name || data?.beneficiary_name || current.account_name || ""),
      }));
      toast.success("Account lookup complete");
      setStatus({ kind: "success", message: "Transfer account lookup completed." });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Lookup failed");
      setStatus({ kind: "error", message: error instanceof Error ? error.message : "Transfer lookup failed." });
    } finally {
      setTransferLookupBusy(false);
    }
  }

  async function submitTransfer() {
    if (!activeVendorId) {
      toast.error("Set an active vendor first");
      setStatus({ kind: "error", message: "Transfer initiation needs an active vendor." });
      return;
    }
    setTransferBusy(true);
    try {
      await api.initiateTransfer({
        amount: Number(transferForm.amount),
        bank_code: transferForm.bank_code,
        account_number: transferForm.account_number,
        account_name: transferForm.account_name,
        remark: transferForm.remark,
        security_answer: transferForm.security_answer,
      });
      toast.success("Transfer sent");
      setStatus({ kind: "success", message: "Transfer initiated successfully." });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Transfer failed");
      setStatus({ kind: "error", message: error instanceof Error ? error.message : "Transfer failed." });
    } finally {
      setTransferBusy(false);
    }
  }

  async function sendWebhook() {
    if (!paymentRef) {
      toast.error("Create or lookup a payment first");
      setStatus({ kind: "error", message: "Webhook replay needs a payment reference." });
      return;
    }
    setWebhookBusy(true);
    try {
      await api.sendSquadWebhook({
        event: "payment.success",
        transaction_ref: paymentRef,
        vendor_id: activeVendorId,
      });
      toast.success("Webhook sent");
      setStatus({ kind: "success", message: "Webhook payload sent successfully." });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Webhook failed");
      setStatus({ kind: "error", message: error instanceof Error ? error.message : "Webhook failed." });
    } finally {
      setWebhookBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Operations"
        subtitle="Drive the payment, wallet, transfer, and webhook endpoints from one place."
      />

      {status ? (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-[#E5E9ED] bg-white px-4 py-3">
          <Badge variant={status.kind === "success" ? "success" : status.kind === "error" ? "blocked" : "info"}>
            {status.kind}
          </Badge>
          <p className="text-[13px] text-[#0B3142]">{status.message}</p>
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <div className="flex flex-col gap-1">
            <h2 className="text-[16px] font-semibold text-[#0B3142]">Vendor session</h2>
            <p className="text-[12px] text-[#4A6B7C]">Choose the vendor that payments and transfers should run under.</p>
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
            <Button className="sm:self-end" onClick={() => void saveVendorSession()}>
              Use ID
            </Button>
          </div>
          <div className="mt-4 grid gap-3 text-[13px] text-[#4A6B7C] sm:grid-cols-4">
            <div>
              <p className="text-[11px] uppercase tracking-wide">Active session</p>
              <p className="mt-1 break-all text-[#0B3142]">{activeVendorId || "None"}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wide">Current vendor</p>
              <p className="mt-1 break-all text-[#0B3142]">{selectedVendor?.business_name || vendor?.business_name || "Unavailable"}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wide">Status</p>
              <p className="mt-1 text-[#0B3142]">
                {selectedVendor?.status || vendor?.status || "Unavailable"}
                {(selectedVendor?.squad_account_id || vendor?.squad_account_id) ? " - Squad active" : ""}
              </p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wide">Payment question</p>
              <p className="mt-1 text-[#0B3142]">{paymentQuestion}</p>
            </div>
          </div>
          <div className="mt-4 max-h-44 overflow-auto rounded-lg border border-[#E5E9ED]">
            {vendorsLoading ? (
              <div className="space-y-2 p-4">
                <div className="h-4 w-3/4 rounded skeleton" />
                <div className="h-4 w-1/2 rounded skeleton" />
                <div className="h-4 w-2/3 rounded skeleton" />
              </div>
            ) : approvedVendors.length ? (
              <ul className="divide-y divide-[#E5E9ED] text-[12px]">
                {approvedVendors.map((item) => (
                  <li key={item.id} className="grid gap-1 px-4 py-3 sm:grid-cols-[1fr_auto] sm:items-center">
                    <div>
                      <p className="font-medium text-[#0B3142]">{item.business_name}</p>
                      <p className="break-all text-[#4A6B7C]">{item.id}</p>
                    </div>
                    <Button size="sm" variant={item.id === activeVendorId ? "successOutline" : "secondary"} onClick={() => selectVendor(item.id)}>
                      {item.id === activeVendorId ? "Selected" : "Use"}
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-4 text-[12px] text-[#4A6B7C]">No approved Squad-active vendors are available yet.</p>
            )}
          </div>
        </Card>

        <Section
          title="Wallet"
          description="Create and inspect the vendor wallet plus recent wallet transactions."
        >
          <div className="flex flex-wrap gap-2">
            <Button leftIcon={<RefreshCw className="h-4 w-4" />} loading={walletBusy} onClick={() => void createWallet()}>
              Create Wallet
            </Button>
            <Button
              variant="secondary"
              leftIcon={<Copy className="h-4 w-4" />}
              onClick={() => {
                if (wallet?.customer_identifier) {
                  void navigator.clipboard.writeText(wallet.customer_identifier);
                  toast.success("Copied customer identifier");
                }
              }}
            >
              Copy ID
            </Button>
          </div>
          <div className="mt-4 grid gap-3 text-[13px] sm:grid-cols-2">
            <div className="rounded-lg bg-[#F8F9FA] p-4">
              <p className="text-[11px] uppercase tracking-wide text-[#8FA3AF]">Virtual account</p>
              <p className="mt-1 text-[#0B3142]">{wallet?.virtual_account_number || "Not assigned"}</p>
              <p className="mt-1 text-[#4A6B7C]">{wallet?.bank || "No bank"}</p>
            </div>
            <div className="rounded-lg bg-[#F8F9FA] p-4">
              <p className="text-[11px] uppercase tracking-wide text-[#8FA3AF]">Status</p>
              <p className="mt-1 text-[#0B3142]">{wallet?.status || "Unavailable"}</p>
              <p className="mt-1 text-[#4A6B7C]">{wallet?.account_name || "No account name"}</p>
            </div>
          </div>
          <div className="mt-4 max-h-56 overflow-auto rounded-lg border border-[#E5E9ED]">
            {(walletTransactions || []).length ? (
              <ul className="divide-y divide-[#E5E9ED] text-[12px]">
                {walletTransactions?.map((tx, index) => (
                  <li key={tx.id || tx.reference || index} className="px-4 py-3">
                    <p className="font-medium text-[#0B3142]">{tx.narration || tx.reference || "Transaction"}</p>
                    <p className="text-[#4A6B7C]">
                      {tx.amount ? `Amount: ${tx.amount}` : "Amount unavailable"} {tx.status ? `• ${tx.status}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-4 text-[12px] text-[#4A6B7C]">No wallet transactions yet.</p>
            )}
          </div>
        </Section>
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        <Section title="Payments" description="Initiate a payment, then look it up by transaction reference.">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label="Amount"
              inputMode="numeric"
              value={paymentForm.amount}
              onChange={(event) => setPaymentForm((current) => ({ ...current, amount: event.target.value }))}
            />
            <Input
              label="Customer Name"
              value={paymentForm.customer_name}
              onChange={(event) => setPaymentForm((current) => ({ ...current, customer_name: event.target.value }))}
            />
            <Input
              label="Customer Email"
              value={paymentForm.customer_email}
              onChange={(event) => setPaymentForm((current) => ({ ...current, customer_email: event.target.value }))}
            />
            <Input
              label="Security Answer"
              type={showPaymentSecurityAnswer ? "text" : "password"}
              value={paymentForm.security_answer}
              onChange={(event) => setPaymentForm((current) => ({ ...current, security_answer: event.target.value }))}
              rightElement={
                <button
                  type="button"
                  className="flex h-7 w-7 items-center justify-center rounded-md text-[#4A6B7C] transition-colors hover:bg-[#F2F4F6]"
                  aria-label={showPaymentSecurityAnswer ? "Hide payment security answer" : "Show payment security answer"}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => setShowPaymentSecurityAnswer((current) => !current)}
                >
                  {showPaymentSecurityAnswer ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
            />
            <Input
              className="sm:col-span-2"
              label="Callback URL"
              value={paymentForm.callback_url}
              onChange={(event) => setPaymentForm((current) => ({ ...current, callback_url: event.target.value }))}
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button loading={paymentBusy} onClick={() => void submitPayment()}>Initiate Payment</Button>
            <Button
              variant="secondary"
              loading={paymentLookupBusy}
              onClick={() => {
                setLookupRef(paymentRef);
                void lookupPayment();
              }}
            >
              Refresh Latest
            </Button>
          </div>
          <div className="mt-4 rounded-lg bg-[#F8F9FA] p-4 text-[12px]">
            <p className="font-medium text-[#0B3142]">Latest transaction ref</p>
            <p className="mt-1 break-all text-[#4A6B7C]">{paymentRef || "None yet"}</p>
          </div>
          <div className="mt-4 rounded-lg border border-[#E5E9ED] bg-white p-4 text-[12px]">
            <p className="font-medium text-[#0B3142]">Payment checkout link</p>
            {paymentCheckoutUrl ? (
              <>
                <a
                  className="mt-1 block break-all text-[#E51E56] underline-offset-2 hover:underline"
                  href={paymentCheckoutUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  {paymentCheckoutUrl}
                </a>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => window.open(paymentCheckoutUrl, "_blank", "noopener,noreferrer")}>
                    Open Payment Page
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    leftIcon={<Copy className="h-3.5 w-3.5" />}
                    onClick={() => {
                      void navigator.clipboard.writeText(paymentCheckoutUrl);
                      toast.success("Payment link copied");
                    }}
                  >
                    Copy Link
                  </Button>
                </div>
              </>
            ) : (
              <p className="mt-1 text-[#4A6B7C]">Initiate a payment to generate a checkout link.</p>
            )}
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto]">
            <Input
              label="Lookup transaction ref"
              value={lookupRef}
              onChange={(event) => setLookupRef(event.target.value)}
            />
            <Button className="sm:self-end" loading={paymentLookupBusy} onClick={() => void lookupPayment()}>
              Lookup
            </Button>
          </div>
          <div className="mt-4 rounded-lg border border-[#E5E9ED] bg-white p-4 text-[12px]">
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap text-[#0B3142]">
              {lookupResult ? JSON.stringify(lookupResult, null, 2) : "Payment lookup result will appear here."}
            </pre>
          </div>
        </Section>

        <Section
          title="Transfers and webhook"
          description="Check account details, submit a transfer, and replay a Squad webhook payload."
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label="Bank Code"
              value={transferForm.bank_code}
              onChange={(event) => setTransferForm((current) => ({ ...current, bank_code: event.target.value }))}
            />
            <Input
              label="Account Number"
              value={transferForm.account_number}
              onChange={(event) => setTransferForm((current) => ({ ...current, account_number: event.target.value }))}
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button loading={transferLookupBusy} onClick={() => void lookupTransferAccount()}>Lookup Account</Button>
            <Button variant="secondary" onClick={() => void sendWebhook()} loading={webhookBusy}>
              Send Webhook
            </Button>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Input
              label="Account Name"
              value={transferForm.account_name}
              onChange={(event) => setTransferForm((current) => ({ ...current, account_name: event.target.value }))}
            />
            <Input
              label="Amount"
              inputMode="numeric"
              value={transferForm.amount}
              onChange={(event) => setTransferForm((current) => ({ ...current, amount: event.target.value }))}
            />
            <Input
              className="sm:col-span-2"
              label="Remark"
              value={transferForm.remark}
              onChange={(event) => setTransferForm((current) => ({ ...current, remark: event.target.value }))}
            />
            <Input
              className="sm:col-span-2"
              label="Security Answer"
              type={showTransferSecurityAnswer ? "text" : "password"}
              value={transferForm.security_answer}
              onChange={(event) => setTransferForm((current) => ({ ...current, security_answer: event.target.value }))}
              rightElement={
                <button
                  type="button"
                  className="flex h-7 w-7 items-center justify-center rounded-md text-[#4A6B7C] transition-colors hover:bg-[#F2F4F6]"
                  aria-label={showTransferSecurityAnswer ? "Hide transfer security answer" : "Show transfer security answer"}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => setShowTransferSecurityAnswer((current) => !current)}
                >
                  {showTransferSecurityAnswer ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
            />
          </div>
          <div className="mt-4 flex">
            <Button loading={transferBusy} leftIcon={<ArrowRight className="h-4 w-4" />} onClick={() => void submitTransfer()}>
              Initiate Transfer
            </Button>
          </div>
          <div className="mt-4 rounded-lg border border-[#E5E9ED] bg-[#F8F9FA] p-4 text-[12px]">
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-[#0B3142]">
              {transferLookup ? JSON.stringify(transferLookup, null, 2) : "Account lookup response will appear here."}
            </pre>
          </div>
          <div className="mt-4 rounded-lg bg-[#F8F9FA] p-4 text-[12px] text-[#4A6B7C]">
            <p className="font-medium text-[#0B3142]">Payments snapshot</p>
            <p className="mt-1">{payments?.length ? `${payments.length} payments returned by GET /api/payments` : "No payments returned yet."}</p>
          </div>
        </Section>
      </section>
    </div>
  );
}
