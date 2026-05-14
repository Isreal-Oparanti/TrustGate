"use client";

import { useRef, useState } from "react";
import { AlertCircle, CheckCircle, FileText, RotateCcw, Trash2, UploadCloud } from "lucide-react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { cn, documentLabel } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

interface DocumentUploadProps {
  docType: string;
  file?: File;
  vendorId?: string;
  required?: boolean;
  uploadState?: "idle" | "uploading" | "success" | "error";
  progress?: number;
  error?: string;
  onRetry?: (docType: string) => void;
  onFileSelected: (docType: string, file: File) => void;
  onRemove: (docType: string) => void;
}

export function DocumentUpload({
  docType,
  file,
  onFileSelected,
  onRemove,
  onRetry,
  progress = 0,
  required = true,
  uploadState = "idle",
  vendorId,
  error,
}: DocumentUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  async function handleFile(nextFile: File) {
    onFileSelected(docType, nextFile);
    if (!vendorId) return;
    setUploading(true);
    try {
      await api.uploadDocument(vendorId, docType, nextFile);
      toast.success(`${documentLabel(docType)} uploaded`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Document upload failed");
    } finally {
      setUploading(false);
    }
  }

  const statusLabel =
    uploadState === "uploading"
      ? `Uploading... ${progress}%`
      : uploadState === "success"
        ? "Uploaded"
        : uploadState === "error"
          ? "Upload failed"
          : file
            ? "Waiting..."
            : "Waiting...";

  const barColor =
    uploadState === "success" ? "#0D9B68" : uploadState === "error" ? "#DC2626" : "#E51E56";

  return (
    <div className="rounded-xl border border-[#E5E9ED] bg-white p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#E8EEF2] text-[#0B3142]">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-[14px] font-semibold text-[#0B3142]">{documentLabel(docType)}</h4>
            <p className="text-[12px] text-[#8FA3AF]">PDF, JPG, PNG - max 10MB</p>
          </div>
        </div>
        <span className="rounded-full bg-[#F2F4F6] px-2 py-0.5 text-[11px] font-medium text-[#4A6B7C]">
          {required ? "Required" : "Optional"}
        </span>
      </div>

      <button
        type="button"
        className={cn(
          "flex min-h-[132px] w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-[#E5E9ED] bg-white p-6 text-center transition-colors",
          "hover:border-[#E51E56] hover:bg-[#FDE8EE]",
          dragging && "border-[#E51E56] bg-[#FDE8EE]",
        )}
        onClick={() => inputRef.current?.click()}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          const dropped = event.dataTransfer.files[0];
          if (dropped) void handleFile(dropped);
        }}
      >
        {uploading ? (
          <Spinner size="md" className="text-[#E51E56]" />
        ) : (
          <UploadCloud className="h-6 w-6 text-[#4A6B7C]" />
        )}
        <span className="mt-3 text-[13px] font-medium text-[#0B3142]">
          Drag and drop or click to upload
        </span>
        <span className="text-[12px] text-[#8FA3AF]">PDF, JPG, PNG - max 10MB</span>
      </button>

      <input
        ref={inputRef}
        className="hidden"
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        onChange={(event) => {
          const selected = event.target.files?.[0];
          if (selected) void handleFile(selected);
        }}
      />

      {file ? (
        <div className="mt-4 rounded-lg bg-[#F8F9FA] px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              {uploadState === "error" ? (
                <AlertCircle className="h-4 w-4 shrink-0 text-[#DC2626]" />
              ) : (
                <CheckCircle className="h-4 w-4 shrink-0 text-[#0D9B68]" />
              )}
              <span className="truncate text-[12px] font-medium text-[#0B3142]">{file.name}</span>
              <span className="text-[11px] text-[#8FA3AF]">{(file.size / 1024 / 1024).toFixed(1)}MB</span>
            </div>
            <Button
              aria-label={`Remove ${documentLabel(docType)}`}
              className="h-8 w-8 px-0"
              variant="ghost"
              onClick={() => onRemove(docType)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
          <div className="mt-3 grid grid-cols-[1fr_auto] items-center gap-3">
            <div className="h-2 overflow-hidden rounded-full bg-[#E8EEF2]">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${uploadState === "idle" ? 0 : progress}%`,
                  backgroundColor: barColor,
                }}
              />
            </div>
            <span className="text-[11px] font-semibold text-[#4A6B7C]">{statusLabel}</span>
          </div>
          {uploadState === "error" ? (
            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-[12px] text-[#DC2626]">{error || "Upload failed. Please try again."}</p>
              {onRetry ? (
                <Button
                  className="h-8 px-3"
                  variant="secondary"
                  leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
                  onClick={() => onRetry(docType)}
                >
                  Retry
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
