"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  BarChart3,
  Brain,
  Check,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Eye,
  EyeOff,
  FileText,
  Globe,
  Loader2,
  MapPin,
  ShieldCheck,
} from "lucide-react";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { DocumentUpload } from "@/components/vendors/DocumentUpload";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { Select } from "@/components/ui/Select";
import { api } from "@/lib/api";
import { squadSupportedBankOptions } from "@/lib/banks";
import { getMerchantPreset, presetOptions } from "@/lib/merchantPresets";
import type { MerchantPreset } from "@/lib/merchantPresets";
import { setActiveVendorId } from "@/lib/session";
import { documentLabel, formatNaira, getTierLabel, tierRequiredDocuments } from "@/lib/utils";
import type { FormState, Tier, VendorCreate, Verification } from "@/types";

type FormField = keyof FormState;
type UploadState = "idle" | "uploading" | "success" | "error";
type VerificationStageId = "idle" | "ocr" | "nlp" | "identity" | "address" | "web" | "scoring";
type VerificationStepId = Exclude<VerificationStageId, "idle">;
type StepStatus = "done" | "active" | "pending";

interface UploadStatus {
  state: UploadState;
  progress: number;
  error?: string;
}

const VERIFICATION_STEPS: Array<{
  id: VerificationStepId;
  label: string;
  icon: typeof FileText;
}> = [
  { id: "ocr", label: "Reading documents", icon: FileText },
  { id: "nlp", label: "Analysing document content", icon: Brain },
  { id: "identity", label: "Verifying identity", icon: ShieldCheck },
  { id: "address", label: "Confirming business address", icon: MapPin },
  { id: "web", label: "Checking web presence", icon: Globe },
  { id: "scoring", label: "Calculating trust score", icon: BarChart3 },
];

const initialForm: FormState = {
  business_name: "",
  tier: "tier2",
  rc_number: "",
  director_name: "",
  business_category: "",
  website_url: "",
  social_media_url: "",
  expected_monthly_volume: "",
  bvn: "",
  nin: "",
  email: "",
  phone: "",
  address: "",
  bank_name: "",
  bank_code: "",
  account_number: "",
  account_name: "",
  payment_security_question: "",
  payment_security_answer: "",
};

const steps = [
  { number: 1, label: "Business Info" },
  { number: 2, label: "Documents" },
  { number: 3, label: "Review" },
];

const businessCategoryOptions = [
  { label: "Select category", value: "" },
  { label: "Retail", value: "retail" },
  { label: "Food & Bev", value: "food" },
  { label: "Tech", value: "tech" },
  { label: "Construction", value: "construction" },
  { label: "Logistics", value: "logistics" },
  { label: "Other", value: "other" },
];

const stepOneFields: FormField[] = [
  "business_name",
  "rc_number",
  "director_name",
  "business_category",
  "bvn",
  "nin",
  "email",
  "phone",
  "address",
];

const bankFields: FormField[] = ["bank_code", "account_number", "account_name"];
const securityFields: FormField[] = ["payment_security_question", "payment_security_answer"];

function nairaToKobo(value: string): number | undefined {
  const amount = Number(value.replace(/[^\d.]/g, ""));
  if (!Number.isFinite(amount) || amount <= 0) return undefined;
  return Math.round(amount * 100);
}

function normalizeProviderPhone(value: string): string {
  return value.trim().replace(/[\s-]/g, "").replace(/^\+/, "");
}

function normalizeBusinessName(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function validate(form: FormState): Partial<Record<FormField, string>> {
  const errors: Partial<Record<FormField, string>> = {};
  const normalizedPhone = normalizeProviderPhone(form.phone);
  if (!form.business_name.trim()) errors.business_name = "Business name is required";
  if (form.tier === "tier3" && !form.rc_number.trim()) errors.rc_number = "RC number is required for companies";
  if (form.rc_number.trim() && !/^RC\s*\d{5,7}$/i.test(form.rc_number.trim())) {
    errors.rc_number = "Use the format RC 1234567";
  }
  if (!form.director_name.trim()) errors.director_name = "Director name is required";
  if (!form.business_category) errors.business_category = "Select a business category";
  if (form.bvn.replace(/\D/g, "").length !== 11) errors.bvn = "Enter an 11 digit BVN";
  if (form.nin.replace(/\D/g, "").length !== 11) errors.nin = "Enter an 11 digit NIN";
  if (!/^\S+@\S+\.\S+$/.test(form.email)) errors.email = "Enter a valid email address";
  if (!/^(234|0)[789][01]\d{8}$/.test(normalizedPhone) || ![11, 13].includes(normalizedPhone.length)) {
    errors.phone = "Use 08012345678 or 2348012345678";
  }
  if (!form.address.trim()) errors.address = "Registered address is required";
  if (!form.bank_code) errors.bank_code = "Select a settlement bank";
  if (!/^\d{10}$/.test(form.account_number.trim())) errors.account_number = "Enter a 10 digit account number";
  if (!form.account_name.trim()) errors.account_name = "Account name is required";
  if (!form.payment_security_question.trim()) errors.payment_security_question = "Security question is required";
  if (!form.payment_security_answer.trim()) errors.payment_security_answer = "Security answer is required";
  return errors;
}

function StepIndicator({ currentStep }: { currentStep: number }) {
  return (
    <Card className="mb-8">
      <div className="grid grid-cols-3 items-start gap-3">
        {steps.map((step, index) => {
          const active = currentStep === step.number;
          const complete = currentStep > step.number;
          return (
            <div key={step.number} className="relative flex flex-col items-center text-center">
              {index < steps.length - 1 ? <span className="absolute left-1/2 top-4 h-0.5 w-full bg-[#E5E9ED]" /> : null}
              <span
                className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2 text-[12px] font-semibold ${
                  complete
                    ? "border-[#0D9B68] bg-[#0D9B68] text-white"
                    : active
                      ? "border-[#E51E56] bg-[#E51E56] text-white"
                      : "border-[#CDD3D9] bg-white text-[#8FA3AF]"
                }`}
              >
                {complete ? <Check className="h-4 w-4" /> : step.number}
              </span>
              <p className={`mt-2 text-[12px] font-medium ${active ? "text-[#E51E56]" : "text-[#4A6B7C]"}`}>
                Step {step.number}
              </p>
              <p className="text-[11px] text-[#8FA3AF]">{step.label}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function formatFileSize(file?: File): string {
  if (!file) return "";
  const sizeMb = file.size / (1024 * 1024);
  if (sizeMb >= 0.1) return `${sizeMb.toFixed(1)}MB`;
  return `${Math.max(1, Math.round(file.size / 1024))}KB`;
}

function pngFilename(filename: string): string {
  return `${filename.replace(/\.[^/.]+$/, "")}.png`;
}

function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
}

function presetDocumentLines(preset: MerchantPreset, docType: string): string[] {
  const data = preset.data;
  const businessName = String(data.business_name ?? "Preset Merchant");
  const directorName = String(data.director_name ?? "Director Name");
  const rcNumber = String(data.rc_number ?? "RC 0000000");
  const address = String(data.address ?? "Registered address unavailable");
  const accountName = String(data.account_name ?? businessName);
  const fraudPreset = preset.name.toLowerCase().includes("fraud");

  if (fraudPreset && docType === "cac_certificate") {
    return [
      "Corporate Affairs Commission",
      "Certificate of Incorporation",
      "Business Name: Global Import Services Ltd",
      "Registration Number: RC 9876543",
      "Director: Tunde Adeyemi",
      "Registered Address: Plot 9, Aba Industrial Market, Abia State",
    ];
  }
  if (fraudPreset && docType === "utility_bill") {
    return [
      "Electricity Distribution Company",
      "Utility Bill",
      "Customer: Tunde Adeyemi",
      "Service Address: 18 Airport Road, Kano, Nigeria",
      "Billing Month: March 2026",
      "Payment Status: Overdue",
    ];
  }
  if (fraudPreset && docType === "directors_id") {
    return [
      "Federal Republic of Nigeria",
      "National Identity Card",
      "Name: Tunde Adeyemi",
      "NIN: 10987654321",
      "Address: 18 Airport Road, Kano, Nigeria",
    ];
  }

  if (docType === "cac_certificate") {
    return [
      "Corporate Affairs Commission",
      "Certificate of Incorporation",
      `Business Name: ${businessName}`,
      `Registration Number: ${rcNumber}`,
      `Director: ${directorName}`,
      `Registered Address: ${address}`,
    ];
  }
  if (docType === "utility_bill") {
    return [
      "Electricity Distribution Company",
      "Utility Bill",
      `Customer: ${businessName}`,
      `Service Address: ${address}`,
      "Billing Month: March 2026",
      "Payment Status: Paid",
    ];
  }
  if (docType === "directors_id") {
    return [
      "Federal Republic of Nigeria",
      "National Identity Card",
      `Name: ${directorName}`,
      `NIN: ${String(data.nin ?? "00000000000")}`,
      `Address: ${address}`,
    ];
  }
  if (docType === "bank_statement") {
    return [
      "Bank Account Statement",
      `Account Name: ${accountName}`,
      `Account Number: ${String(data.account_number ?? "0000000000")}`,
      `Business: ${businessName}`,
      "Statement Period: January 2026 - March 2026",
    ];
  }
  return [
    documentLabel(docType),
    `Business Name: ${businessName}`,
    `Registration Number: ${rcNumber}`,
    `Director: ${directorName}`,
    `Registered Address: ${address}`,
  ];
}

async function createPresetDocumentFile(preset: MerchantPreset, docType: string, filename: string): Promise<File> {
  const canvas = window.document.createElement("canvas");
  canvas.width = 1200;
  canvas.height = 1600;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Could not prepare preset document");

  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "#0B3142";
  ctx.lineWidth = 6;
  ctx.strokeRect(56, 56, canvas.width - 112, canvas.height - 112);
  ctx.fillStyle = "#0B3142";
  ctx.font = "700 54px Arial";
  ctx.fillText("TrustGate Demo Document", 110, 150);
  ctx.font = "400 30px Arial";
  ctx.fillStyle = "#4A6B7C";
  ctx.fillText("Generated from merchant preset for automated backend upload", 110, 205);
  ctx.fillStyle = "#E51E56";
  ctx.fillRect(110, 255, 150, 10);

  ctx.fillStyle = "#0B3142";
  ctx.font = "700 42px Arial";
  ctx.fillText(documentLabel(docType), 110, 350);
  ctx.font = "400 36px Arial";

  presetDocumentLines(preset, docType).forEach((line, index) => {
    ctx.fillText(line, 110, 445 + index * 78);
  });

  ctx.font = "400 28px Arial";
  ctx.fillStyle = "#4A6B7C";
  ctx.fillText("This file is generated locally and uploaded through the normal document API.", 110, 1425);

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((nextBlob) => {
      if (nextBlob) resolve(nextBlob);
      else reject(new Error("Could not create preset document"));
    }, "image/png");
  });

  return new File([blob], pngFilename(filename), { type: "image/png", lastModified: Date.now() });
}

async function loadPresetDocumentFile(preset: MerchantPreset, docType: string, docInfo: MerchantPreset["documents"][string]): Promise<File> {
  if (!docInfo.sourcePath) {
    return createPresetDocumentFile(preset, docType, docInfo.filename);
  }

  const response = await fetch(`${apiBaseUrl()}${docInfo.sourcePath}`);
  if (!response.ok) {
    throw new Error(`Could not load ${documentLabel(docType)} from preset source`);
  }
  const blob = await response.blob();
  return new File([blob], docInfo.filename, {
    type: blob.type || "image/png",
    lastModified: Date.now(),
  });
}

function UploadedDocumentList({
  docTypes,
  documents,
  statuses,
}: {
  docTypes: string[];
  documents: Record<string, File>;
  statuses: Record<string, UploadStatus>;
}) {
  return (
    <div>
      <p className="text-[12px] font-semibold uppercase tracking-wide text-[#4A6B7C]">Documents uploaded</p>
      <div className="mt-3 space-y-2">
      {docTypes.map((docType) => {
        const status = statuses[docType] || { state: "idle", progress: 0 };
        const file = documents[docType];

        return (
          <div key={docType} className="grid grid-cols-[18px_minmax(120px,1fr)_minmax(0,1fr)_54px] items-center gap-2 text-[12px]">
            {status.state === "success" ? (
              <CheckCircle className="h-4 w-4 text-[#0D9B68]" />
            ) : status.state === "uploading" ? (
              <Loader2 className="h-4 w-4 animate-spin text-[#E51E56]" />
            ) : status.state === "error" ? (
              <AlertCircle className="h-4 w-4 text-[#DC2626]" />
            ) : (
              <span className="h-2 w-2 rounded-full bg-[#CDD3D9]" />
            )}
            <span className="font-medium text-[#0B3142]">{documentLabel(docType)}</span>
            <span className="truncate text-[#4A6B7C]">{file?.name || "Waiting..."}</span>
            <span className="text-right text-[#8FA3AF]">{formatFileSize(file)}</span>
            {status.state === "error" ? (
              <p className="col-span-4 text-[12px] text-[#DC2626]">{status.error}</p>
            ) : null}
          </div>
        );
      })}
      </div>
    </div>
  );
}

function VerificationProgressPanel({
  docTypes,
  documents,
  stage,
  statuses,
}: {
  docTypes: string[];
  documents: Record<string, File>;
  stage: VerificationStageId;
  statuses: Record<string, UploadStatus>;
}) {
  const activeIndex = Math.max(0, VERIFICATION_STEPS.findIndex((item) => item.id === stage));
  const stepStatus = Object.fromEntries(
    VERIFICATION_STEPS.map((step, index) => [
      step.id,
      index < activeIndex ? "done" : index === activeIndex ? "active" : "pending",
    ]),
  ) as Record<VerificationStepId, StepStatus>;

  return (
    <div className="mt-8 rounded-xl border border-[#E5E9ED] bg-white p-6 text-[#0B3142]">
      <UploadedDocumentList docTypes={docTypes} documents={documents} statuses={statuses} />

      <div className="my-5 h-px bg-[#E5E9ED]" />

      <div>
        <p className="text-[13px] font-semibold text-[#0B3142]">AI Verification in Progress</p>
        <div className="mt-4 space-y-3">
          {VERIFICATION_STEPS.map((step) => {
            const Icon = step.icon;
            const status = stepStatus[step.id];
            return (
              <div key={step.id} className="flex items-center gap-3">
                <div
                  className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${
                    status === "done" ? "bg-[#E6F7F1]" : status === "active" ? "bg-[#FDE8EE]" : "bg-[#F2F4F6]"
                  }`}
                >
                  {status === "done" ? (
                    <CheckCircle className="h-4 w-4 text-[#0D9B68]" />
                  ) : status === "active" ? (
                    <Loader2 className="h-4 w-4 animate-spin text-[#E51E56]" />
                  ) : (
                    <Icon className="h-4 w-4 text-[#8FA3AF]" />
                  )}
                </div>
                <span
                  className={`text-[13px] ${
                    status === "done"
                      ? "font-medium text-[#0D9B68]"
                      : status === "active"
                        ? "font-medium text-[#0B3142]"
                        : "text-[#8FA3AF]"
                  }`}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function NewVendorPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<FormState>(initialForm);
  const [touched, setTouched] = useState<Partial<Record<FormField, boolean>>>({});
  const [showBvn, setShowBvn] = useState(false);
  const [showNin, setShowNin] = useState(false);
  const [showSecurityAnswer, setShowSecurityAnswer] = useState(false);
  const [documents, setDocuments] = useState<Record<string, File>>({});
  const [uploadStatuses, setUploadStatuses] = useState<Record<string, UploadStatus>>({});
  const [createdVendorId, setCreatedVendorId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [viewingReport, setViewingReport] = useState(false);
  const [approvingVendor, setApprovingVendor] = useState(false);
  const [vendorApproved, setVendorApproved] = useState(false);
  const [isReportPending, startReportTransition] = useTransition();
  const [checkingBusinessName, setCheckingBusinessName] = useState(false);
  const [duplicateBusinessName, setDuplicateBusinessName] = useState<string | null>(null);
  const [verificationStage, setVerificationStage] = useState<VerificationStageId>("idle");
  const [verificationResult, setVerificationResult] = useState<Verification | null>(null);
  const errors = {
    ...validate(form),
    ...(duplicateBusinessName && normalizeBusinessName(duplicateBusinessName) === normalizeBusinessName(form.business_name)
      ? { business_name: "Business name already exists" }
      : {}),
  };
  const requiredDocs = useMemo(() => tierRequiredDocuments(form.tier), [form.tier]);

  async function loadPreset(presetName: string) {
    const preset = getMerchantPreset(presetName);
    if (!preset) return;

    // Load form data
    setForm((current) => ({
      ...current,
      ...preset.data,
    }));

    const simulatedDocs: Record<string, File> = {};
    const simulatedStatuses: Record<string, UploadStatus> = {};

    try {
      await Promise.all(Object.entries(preset.documents).map(async ([docType, docInfo]) => {
        simulatedDocs[docType] = await loadPresetDocumentFile(preset, docType, docInfo);
        simulatedStatuses[docType] = {
          state: "idle",
          progress: 0,
        };
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not load preset documents";
      toast.error(message);
      return;
    }

    setDocuments(simulatedDocs);
    setUploadStatuses(simulatedStatuses);
    setTouched((current) => ({ ...current, business_name: true }));

    if (typeof preset.data.business_name === "string") {
      void checkBusinessNameAvailability(preset.data.business_name);
    }

    // Show success toast
    toast.success("Demo merchant loaded. Documents will upload on submit.", {
      duration: 3000,
    });
  }

  function updateField(field: FormField, value: string) {
    if (field === "business_name") {
      setDuplicateBusinessName(null);
    }
    setForm((current) => ({ ...current, [field]: value }));
  }

  function markTouched(field: FormField) {
    setTouched((current) => ({ ...current, [field]: true }));
  }

  async function checkBusinessNameAvailability(name = form.business_name): Promise<boolean> {
    const normalized = normalizeBusinessName(name);
    if (!normalized) return false;

    setCheckingBusinessName(true);
    try {
      const vendors = await api.getVendors();
      const duplicate = vendors.find((vendor) => normalizeBusinessName(vendor.business_name) === normalized);
      if (duplicate) {
        setDuplicateBusinessName(duplicate.business_name);
        markTouched("business_name");
        toast.error("Business name already exists. Use a unique business name.");
        return false;
      }
      setDuplicateBusinessName(null);
      return true;
    } catch {
      return true;
    } finally {
      setCheckingBusinessName(false);
    }
  }

  function setDocStatus(docType: string, status: UploadStatus) {
    setUploadStatuses((current) => ({ ...current, [docType]: status }));
  }

  async function canContinueBusiness() {
    setTouched((current) => ({
      ...current,
      ...Object.fromEntries(stepOneFields.map((field) => [field, true])),
    }));
    if (checkingBusinessName) {
      toast.loading("Checking business name...", { id: "business-name-check" });
      return false;
    }
    if (!stepOneFields.every((field) => !errors[field])) return false;
    const businessNameAvailable = await checkBusinessNameAvailability();
    return businessNameAvailable && !checkingBusinessName;
  }

  function canContinueDocuments() {
    setTouched((current) => ({
      ...current,
      ...Object.fromEntries([...bankFields, ...securityFields].map((field) => [field, true])),
    }));
    const missing = requiredDocs.filter((doc) => !documents[doc]);
    if (missing.length > 0) {
      toast.error(`Upload ${documentLabel(missing[0])} before continuing`);
      return false;
    }
    return [...bankFields, ...securityFields].every((field) => !errors[field]);
  }

  async function pollVerification(vendorId: string) {
    const maxAttempts = 45;
    let attempts = 0;

    return new Promise<Verification>((resolve, reject) => {
      const interval = window.setInterval(async () => {
        attempts += 1;
        if (attempts > maxAttempts) {
          window.clearInterval(interval);
          reject(new Error("Verification timeout"));
          return;
        }

        try {
          const result = await api.getVerification(vendorId);
          if (result.verdict && result.verdict !== "pending" && result.status !== "not_started") {
            window.clearInterval(interval);
            resolve(result);
          }
        } catch {
          // 404/not_started is transient while verification is warming up.
        }
      }, 4000);
    });
  }

  async function uploadDocumentForVendor(vendorId: string, docType: string) {
    const file = documents[docType];
    if (!file) return;

    setDocStatus(docType, { state: "uploading", progress: 35 });
    try {
      setDocStatus(docType, { state: "uploading", progress: 67 });
      await api.uploadDocument(vendorId, docType, file);
      setDocStatus(docType, { state: "success", progress: 100 });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Upload failed. Please try again.";
      setDocStatus(docType, { state: "error", progress: 100, error: message });
      throw new Error(message);
    }
  }

  async function retryDocumentUpload(docType: string) {
    if (!createdVendorId) {
      toast.error("Create the vendor before retrying upload.");
      return;
    }
    try {
      await uploadDocumentForVendor(createdVendorId, docType);
      toast.success(`${documentLabel(docType)} uploaded`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Upload failed. Please try again.";
      toast.error(message);
    }
  }

  async function submitVendor() {
    const missing = requiredDocs.filter((doc) => !documents[doc]);
    if (Object.keys(errors).length > 0 || missing.length > 0) {
      toast.error("Complete all required fields and documents");
      setTouched((current) => ({
        ...current,
        ...Object.fromEntries([...stepOneFields, ...bankFields, ...securityFields].map((field) => [field, true])),
      }));
      return;
    }

    if (!createdVendorId) {
      const businessNameAvailable = await checkBusinessNameAvailability();
      if (!businessNameAvailable) return;
    }

    setSubmitting(true);
    setVerificationStage("ocr");
    const toastId = toast.loading("Creating vendor...");
    let stageTimer: number | undefined;
    try {
      let vendorId = createdVendorId;
      if (!vendorId) {
        const monthlyVolume = nairaToKobo(form.expected_monthly_volume);
        const payload: VendorCreate = {
          business_name: form.business_name.trim(),
          rc_number: form.tier === "tier1" ? null : form.rc_number.trim() || null,
          director_name: form.director_name.trim(),
          business_category: form.business_category,
          website_url: form.website_url.trim(),
          social_media_url: form.social_media_url.trim(),
          ...(monthlyVolume ? { expected_monthly_volume: monthlyVolume } : {}),
          bank_name: form.bank_name,
          bank_code: form.bank_code,
          account_number: form.account_number.trim(),
          account_name: form.account_name.trim(),
          settlement_account_name: form.account_name.trim(),
          settlement_account_number: form.account_number.trim(),
          settlement_bank_code: form.bank_code,
          settlement_bank: form.bank_name,
          payment_security_question: form.payment_security_question.trim(),
          payment_security_answer: form.payment_security_answer.trim(),
          bvn: form.bvn.replace(/\D/g, ""),
          nin: form.nin.replace(/\D/g, ""),
          email: form.email.trim(),
          phone: normalizeProviderPhone(form.phone),
          address: form.address.trim(),
          tier: form.tier,
        };
        const vendor = await api.createVendor(payload);
        vendorId = vendor.id;
        setCreatedVendorId(vendor.id);
        setActiveVendorId(vendor.id);
      }

      toast.loading("Uploading documents...", { id: toastId });
      for (const docType of requiredDocs) {
        if (uploadStatuses[docType]?.state === "success") continue;
        await uploadDocumentForVendor(vendorId, docType);
      }

      setVerificationStage("ocr");
      toast.loading("Running AI verification...", { id: toastId });
      const stageOrder: VerificationStepId[] = ["ocr", "nlp", "identity", "address", "web", "scoring"];
      let stageIndex = 0;
      stageTimer = window.setInterval(() => {
        stageIndex = Math.min(stageIndex + 1, stageOrder.length - 1);
        setVerificationStage(stageOrder[stageIndex]);
      }, 8000);
      await api.runVerification(vendorId, { wait: false });
      const completed = await pollVerification(vendorId);
      window.clearInterval(stageTimer);
      stageTimer = undefined;
      setVerificationStage("scoring");
      setVerificationResult(completed);
      toast.success("Verification complete", { id: toastId });
    } catch (error) {
      if (stageTimer) window.clearInterval(stageTimer);
      const message =
        error instanceof Error && error.message === "Verification timeout"
          ? "Verification is taking longer than expected. You can check back later."
          : error instanceof Error
            ? error.message
            : "Verification failed. Please try again.";
      toast.error(message, { id: toastId });
      setSubmitting(false);
      setVerificationStage("idle");
    }
  }

  function viewFullReport() {
    if (!verificationResult) return;
    setViewingReport(true);
    startReportTransition(() => {
      router.push(`/dashboard/vendors/${verificationResult.vendor_id}`);
    });
  }

  async function approveVendor() {
    if (!verificationResult || approvingVendor || vendorApproved) return;

    setApprovingVendor(true);
    const toastId = toast.loading("Approving vendor...");
    try {
      await api.updateVendorStatus(verificationResult.vendor_id, "approved");
      setVendorApproved(true);
      toast.success("Vendor approved - Squad merchant account created", { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not approve vendor", { id: toastId });
    } finally {
      setApprovingVendor(false);
    }
  }

  const monthlyVolume = nairaToKobo(form.expected_monthly_volume);
  const selectedCategory = businessCategoryOptions.find((option) => option.value === form.business_category)?.label;

  return (
    <div>
      <PageHeader
        title="Register New Vendor"
        subtitle="Capture vendor details, collect required documents, and start AI verification."
        action={
          <div className="w-full sm:w-auto">
            <Select
              options={presetOptions}
              value=""
              onChange={(event) => {
                if (event.target.value) {
                  void loadPreset(event.target.value);
                  // Reset select after loading
                  event.target.value = "";
                }
              }}
            />
          </div>
        }
      />
      <StepIndicator currentStep={step} />

      {verificationResult ? (
        <Card className="flex min-h-[420px] flex-col items-center justify-center text-center">
          <motion.div initial={{ scale: 0.86, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.5 }}>
            <ScoreRing score={verificationResult.trust_score ?? 0} size="lg" />
          </motion.div>
          <Badge className="mt-5" variant={verificationResult.verdict}>
            {verificationResult.verdict}
          </Badge>
          <h3 className="mt-5 text-[22px] font-bold text-[#0B3142]">Verification complete</h3>
          <p className="mt-1 text-[13px] text-[#4A6B7C]">The AI report is ready for compliance review.</p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <Button
              size="lg"
              loading={viewingReport || isReportPending}
              onClick={viewFullReport}
            >
              View Full Report
            </Button>
            <Button
              className={vendorApproved ? "blur-[0.5px]" : undefined}
              size="lg"
              variant="success"
              loading={approvingVendor}
              disabled={vendorApproved}
              leftIcon={<CheckCircle className="h-4 w-4" />}
              onClick={() => void approveVendor()}
            >
              {vendorApproved ? "Approved" : "Approve"}
            </Button>
          </div>
        </Card>
      ) : (
        <Card>
          {step === 1 ? (
            <div>
              <div className="grid gap-5 md:grid-cols-2">
                <Input
                  label="Business Name"
                  value={form.business_name}
                  error={touched.business_name ? errors.business_name : undefined}
                  helperText={checkingBusinessName ? "Checking business name..." : undefined}
                  onBlur={() => {
                    markTouched("business_name");
                    void checkBusinessNameAvailability();
                  }}
                  onChange={(event) => updateField("business_name", event.target.value)}
                />
                <div>
                  <span className="mb-1.5 block text-[13px] font-medium leading-normal text-[#0B3142]">
                    Registration Type
                  </span>
                  <div className="grid grid-cols-3 gap-2">
                    {(["tier1", "tier2", "tier3"] as Tier[]).map((tier) => (
                      <button
                        key={tier}
                        type="button"
                        className={`h-10 rounded-lg border-[1.5px] px-3 text-[12px] font-medium transition-colors ${
                          form.tier === tier
                            ? "border-[#E51E56] bg-[#FDE8EE] text-[#E51E56]"
                            : "border-[#E5E9ED] bg-white text-[#4A6B7C] hover:bg-[#F8F9FA]"
                        }`}
                        onClick={() => setForm((current) => ({ ...current, tier, rc_number: tier === "tier1" ? "" : current.rc_number }))}
                      >
                        {getTierLabel(tier)}
                      </button>
                    ))}
                  </div>
                </div>
                {form.tier !== "tier1" ? (
                  <Input
                    label="RC Number (CAC Registration Number)"
                    placeholder="RC 1234567"
                    helperText="Leave blank if registering as an individual (Tier 1)"
                    value={form.rc_number}
                    error={touched.rc_number ? errors.rc_number : undefined}
                    onBlur={() => markTouched("rc_number")}
                    onChange={(event) => updateField("rc_number", event.target.value)}
                  />
                ) : null}
                <Input
                  label="Director Name"
                  value={form.director_name}
                  error={touched.director_name ? errors.director_name : undefined}
                  onBlur={() => markTouched("director_name")}
                  onChange={(event) => updateField("director_name", event.target.value)}
                />
                <Select
                  label="Business Category"
                  options={businessCategoryOptions}
                  value={form.business_category}
                  error={touched.business_category ? errors.business_category : undefined}
                  onBlur={() => markTouched("business_category")}
                  onChange={(event) => updateField("business_category", event.target.value)}
                />
                <Input
                  label="Website URL"
                  placeholder="https://"
                  value={form.website_url}
                  onChange={(event) => updateField("website_url", event.target.value)}
                />
                <Input
                  label="Social Media"
                  placeholder="https://instagram.com/..."
                  value={form.social_media_url}
                  onChange={(event) => updateField("social_media_url", event.target.value)}
                />
                <Input
                  label="Expected Monthly Volume (NGN)"
                  placeholder="2500000"
                  helperText="Approximate naira volume per month"
                  inputMode="numeric"
                  value={form.expected_monthly_volume}
                  onChange={(event) => updateField("expected_monthly_volume", event.target.value)}
                />
                <Input
                  label="BVN"
                  type={showBvn ? "text" : "password"}
                  value={form.bvn}
                  error={touched.bvn ? errors.bvn : undefined}
                  onBlur={() => markTouched("bvn")}
                  onChange={(event) => updateField("bvn", event.target.value)}
                  rightElement={
                    <button
                      type="button"
                      className="text-[#4A6B7C]"
                      aria-label={showBvn ? "Hide BVN" : "Show BVN"}
                      onClick={() => setShowBvn((value) => !value)}
                    >
                      {showBvn ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                />
                <Input
                  label="NIN"
                  type={showNin ? "text" : "password"}
                  value={form.nin}
                  error={touched.nin ? errors.nin : undefined}
                  onBlur={() => markTouched("nin")}
                  onChange={(event) => updateField("nin", event.target.value)}
                  rightElement={
                    <button
                      type="button"
                      className="text-[#4A6B7C]"
                      aria-label={showNin ? "Hide NIN" : "Show NIN"}
                      onClick={() => setShowNin((value) => !value)}
                    >
                      {showNin ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                />
                <Input
                  label="Email"
                  type="email"
                  value={form.email}
                  error={touched.email ? errors.email : undefined}
                  onBlur={() => markTouched("email")}
                  onChange={(event) => updateField("email", event.target.value)}
                />
                <Input
                  label="Phone"
                  value={form.phone}
                  error={touched.phone ? errors.phone : undefined}
                  onBlur={() => markTouched("phone")}
                  onChange={(event) => updateField("phone", event.target.value)}
                />
                <Input
                  className="md:col-span-2"
                  label="Registered Address"
                  value={form.address}
                  error={touched.address ? errors.address : undefined}
                  onBlur={() => markTouched("address")}
                  onChange={(event) => updateField("address", event.target.value)}
                />
              </div>
              <div className="mt-8 flex justify-end">
                <Button
                  loading={checkingBusinessName}
                  disabled={checkingBusinessName}
                  rightIcon={<ChevronRight className="h-4 w-4" />}
                  onClick={() => {
                    void canContinueBusiness().then((canContinue) => {
                      if (canContinue) setStep(2);
                    });
                  }}
                >
                  {checkingBusinessName ? "Checking..." : "Continue"}
                </Button>
              </div>
            </div>
          ) : null}

          {step === 2 ? (
            <div>
              <div className="grid gap-4">
                {requiredDocs.map((docType) => {
                  const status = uploadStatuses[docType] || { state: "idle", progress: 0 };
                  return (
                    <DocumentUpload
                      key={docType}
                      docType={docType}
                      file={documents[docType]}
                      vendorId={createdVendorId || undefined}
                      uploadState={status.state}
                      progress={status.progress}
                      error={status.error}
                      onRetry={(type) => void retryDocumentUpload(type)}
                      onFileSelected={(type, file) => {
                        setDocuments((current) => ({ ...current, [type]: file }));
                        setDocStatus(type, { state: "idle", progress: 0 });
                      }}
                      onRemove={(type) => {
                        setDocuments((current) => {
                          const next = { ...current };
                          delete next[type];
                          return next;
                        });
                        setUploadStatuses((current) => {
                          const next = { ...current };
                          delete next[type];
                          return next;
                        });
                      }}
                    />
                  );
                })}
              </div>

              <div className="mt-8 border-t border-[#E5E9ED] pt-6">
                <h3 className="text-[18px] font-semibold text-[#0B3142]">Settlement Bank Details</h3>
                <p className="mt-1 text-[12px] text-[#4A6B7C]">This is where Squad will settle your payments</p>
                <div className="mt-5 grid gap-5 md:grid-cols-3">
                  <Select
                    label="Bank Name"
                    options={squadSupportedBankOptions}
                    value={form.bank_code}
                    error={touched.bank_code ? errors.bank_code : undefined}
                    onBlur={() => markTouched("bank_code")}
                    onChange={(event) => {
                      const bank = squadSupportedBankOptions.find((option) => option.value === event.target.value);
                      setForm((current) => ({
                        ...current,
                        bank_code: event.target.value,
                        bank_name: bank?.label === "Select bank" ? "" : bank?.label || "",
                      }));
                    }}
                  />
                  <Input
                    label="Account Number"
                    inputMode="numeric"
                    maxLength={10}
                    value={form.account_number}
                    error={touched.account_number ? errors.account_number : undefined}
                    onBlur={() => markTouched("account_number")}
                    onChange={(event) => updateField("account_number", event.target.value.replace(/\D/g, ""))}
                  />
                  <Input
                    label="Account Name"
                    helperTone="danger"
                    helperText="Must match business name"
                    value={form.account_name}
                    error={touched.account_name ? errors.account_name : undefined}
                    onBlur={() => markTouched("account_name")}
                    onChange={(event) => updateField("account_name", event.target.value)}
                  />
                </div>
              </div>

              <div className="mt-8 border-t border-[#E5E9ED] pt-6">
                <h3 className="text-[18px] font-semibold text-[#0B3142]">Payment Security</h3>
                <p className="mt-1 text-[12px] text-[#4A6B7C]">This will be used when the vendor initiates payments.</p>
                <div className="mt-5 grid gap-5 md:grid-cols-2">
                  <Input
                    label="Security Question"
                    value={form.payment_security_question}
                    error={touched.payment_security_question ? errors.payment_security_question : undefined}
                    onBlur={() => markTouched("payment_security_question")}
                    onChange={(event) => updateField("payment_security_question", event.target.value)}
                  />
                  <Input
                    label="Security Answer"
                    type={showSecurityAnswer ? "text" : "password"}
                    value={form.payment_security_answer}
                    error={touched.payment_security_answer ? errors.payment_security_answer : undefined}
                    onBlur={() => markTouched("payment_security_answer")}
                    onChange={(event) => updateField("payment_security_answer", event.target.value)}
                    rightElement={
                      <button
                        type="button"
                        className="flex h-7 w-7 items-center justify-center rounded-md text-[#4A6B7C] transition-colors hover:bg-[#F2F4F6]"
                        aria-label={showSecurityAnswer ? "Hide security answer" : "Show security answer"}
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => setShowSecurityAnswer((current) => !current)}
                      >
                        {showSecurityAnswer ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    }
                  />
                </div>
              </div>

              <div className="mt-8 flex justify-between">
                <Button
                  variant="secondary"
                  leftIcon={<ChevronLeft className="h-4 w-4" />}
                  onClick={() => setStep(1)}
                >
                  Back
                </Button>
                <Button
                  rightIcon={<ChevronRight className="h-4 w-4" />}
                  onClick={() => {
                    if (canContinueDocuments()) setStep(3);
                  }}
                >
                  Continue
                </Button>
              </div>
            </div>
          ) : null}

          {step === 3 ? (
            <div>
              <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
                <div className="rounded-xl bg-[#F8F9FA] p-5">
                  <h3 className="text-[18px] font-semibold text-[#0B3142]">Business Information</h3>
                  <dl className="mt-4 grid gap-3 text-[13px] md:grid-cols-2">
                    {[
                      ["Business Name", form.business_name],
                      ["Tier", getTierLabel(form.tier)],
                      ["RC Number", form.rc_number || "Not required"],
                      ["Director Name", form.director_name],
                      ["Business Category", selectedCategory || "Not selected"],
                      ["Website", form.website_url || "Optional"],
                      ["Social Media", form.social_media_url || "Optional"],
                      ["Expected Monthly Volume", monthlyVolume ? formatNaira(monthlyVolume) : "Not provided"],
                      ["BVN", "***********"],
                      ["NIN", "***********"],
                      ["Email", form.email],
                      ["Phone", form.phone],
                      ["Address", form.address],
                      ["Bank", form.bank_name],
                      ["Account Number", form.account_number],
                      ["Account Name", form.account_name],
                      ["Security Question", form.payment_security_question],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <dt className="text-[11px] font-semibold uppercase tracking-wide text-[#8FA3AF]">
                          {label}
                        </dt>
                        <dd className="mt-1 break-words font-medium text-[#0B3142]">{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
                <div className="rounded-xl border border-[#E5E9ED] p-5">
                  <h3 className="text-[18px] font-semibold text-[#0B3142]">Documents</h3>
                  <div className="mt-4 space-y-3">
                    {requiredDocs.map((docType) => (
                      <div key={docType} className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <Check className="h-4 w-4 text-[#0D9B68]" />
                          <span className="text-[13px] font-medium text-[#0B3142]">{documentLabel(docType)}</span>
                        </div>
                        <span className="truncate text-right text-[11px] text-[#8FA3AF]">{documents[docType]?.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {submitting ? (
                <VerificationProgressPanel
                  docTypes={requiredDocs}
                  documents={documents}
                  stage={verificationStage === "idle" ? "ocr" : verificationStage}
                  statuses={uploadStatuses}
                />
              ) : Object.values(uploadStatuses).some((status) => status.state === "error") ? (
                <div className="mt-8 flex items-start gap-3 rounded-xl bg-[#FEE2E2] p-4 text-[#991B1B]">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <p className="text-[13px]">Fix the failed upload, then submit again.</p>
                </div>
              ) : null}

              <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:justify-between">
                <Button
                  variant="secondary"
                  leftIcon={<ChevronLeft className="h-4 w-4" />}
                  onClick={() => setStep(2)}
                  disabled={submitting}
                >
                  Back
                </Button>
                <Button
                  className="sm:min-w-[260px]"
                  size="lg"
                  loading={submitting}
                  leftIcon={<ShieldCheck className="h-4 w-4" />}
                  onClick={() => void submitVendor()}
                >
                  Submit for Verification
                </Button>
              </div>
            </div>
          ) : null}
        </Card>
      )}
    </div>
  );
}
