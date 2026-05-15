"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, Database, RefreshCw, Trash2 } from "lucide-react";
import useSWR from "swr";
import toast from "react-hot-toast";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { formatDate, getTierLabel } from "@/lib/utils";

export default function AdminPage() {
  const { data: vendors, error, isLoading, mutate } = useSWR("admin-vendors", api.getAdminVendors);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const sortedVendors = useMemo(() => vendors || [], [vendors]);
  const selectedCount = selectedIds.length;
  const allSelected = sortedVendors.length > 0 && selectedCount === sortedVendors.length;

  async function deleteVendor(id: string, name: string) {
    const confirmed = window.confirm(`Delete ${name} and all related verification data? This cannot be undone.`);
    if (!confirmed) return;

    setDeletingId(id);
    try {
      await api.deleteAdminVendor(id);
      await mutate((current) => current?.filter((vendor) => vendor.id !== id), { revalidate: false });
      setSelectedIds((current) => current.filter((selectedId) => selectedId !== id));
      toast.success("Vendor deleted from the database");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete vendor");
    } finally {
      setDeletingId(null);
    }
  }

  function toggleVendorSelection(id: string) {
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((selectedId) => selectedId !== id) : [...current, id],
    );
  }

  function toggleAllVendors() {
    setSelectedIds(allSelected ? [] : sortedVendors.map((vendor) => vendor.id));
  }

  async function deleteSelectedVendors() {
    if (selectedIds.length === 0) return;
    const confirmed = window.confirm(
      `Delete ${selectedIds.length} selected vendor${selectedIds.length === 1 ? "" : "s"} and all related data? This cannot be undone.`,
    );
    if (!confirmed) return;

    setBulkDeleting(true);
    try {
      await Promise.all(selectedIds.map((id) => api.deleteAdminVendor(id)));
      await mutate((current) => current?.filter((vendor) => !selectedIds.includes(vendor.id)), { revalidate: false });
      toast.success(`Deleted ${selectedIds.length} vendor${selectedIds.length === 1 ? "" : "s"}`);
      setSelectedIds([]);
    } catch (err) {
      await mutate();
      toast.error(err instanceof Error ? err.message : "Could not delete selected vendors");
    } finally {
      setBulkDeleting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#F8F9FA] px-5 py-8 lg:px-10">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex flex-col gap-4 rounded-xl border border-[#E5E9ED] bg-white p-5 card-shadow md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#0B3142] text-white">
              <Database className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-[24px] font-bold text-[#0B3142]">TrustGate Admin</h1>
              <p className="text-[13px] text-[#4A6B7C]">Delete test vendors and their related verification records.</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="danger"
              leftIcon={<Trash2 className="h-4 w-4" />}
              loading={bulkDeleting}
              disabled={selectedCount === 0}
              onClick={() => void deleteSelectedVendors()}
            >
              Delete Selected{selectedCount ? ` (${selectedCount})` : ""}
            </Button>
            <Button
              variant="secondary"
              leftIcon={<RefreshCw className="h-4 w-4" />}
              onClick={() => void mutate()}
            >
              Refresh
            </Button>
          </div>
        </div>

        <Card>
          <div className="mb-5 flex items-center gap-2 rounded-lg bg-[#FEF3C7] px-4 py-3 text-[#92400E]">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <p className="text-[13px]">
              Deletes cascade through documents, flags, verifications, and transactions for that vendor.
            </p>
          </div>

          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, index) => (
                <div key={index} className="h-14 rounded-lg skeleton" />
              ))}
            </div>
          ) : error ? (
            <div className="rounded-lg bg-[#FEE2E2] p-5 text-[13px] text-[#991B1B]">
              Failed to load admin vendors.
            </div>
          ) : sortedVendors.length === 0 ? (
            <div className="rounded-lg bg-[#F8F9FA] p-8 text-center text-[13px] text-[#4A6B7C]">
              No vendors in the database.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-[#E5E9ED] text-[11px] uppercase tracking-wide text-[#8FA3AF]">
                    <th className="w-11 px-3 py-3">
                      <input
                        type="checkbox"
                        aria-label="Select all vendors"
                        checked={allSelected}
                        onChange={toggleAllVendors}
                        className="h-4 w-4 rounded border-[#CDD3D9] accent-[#E51E56]"
                      />
                    </th>
                    <th className="px-3 py-3">Vendor</th>
                    <th className="px-3 py-3">Tier</th>
                    <th className="px-3 py-3">Status</th>
                    <th className="px-3 py-3">Squad ID</th>
                    <th className="px-3 py-3">RC Number</th>
                    <th className="px-3 py-3">Created</th>
                    <th className="px-3 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E9ED]">
                  {sortedVendors.map((vendor) => (
                    <tr key={vendor.id} className="text-[13px] text-[#0B3142]">
                      <td className="px-3 py-4">
                        <input
                          type="checkbox"
                          aria-label={`Select ${vendor.business_name}`}
                          checked={selectedIds.includes(vendor.id)}
                          onChange={() => toggleVendorSelection(vendor.id)}
                          className="h-4 w-4 rounded border-[#CDD3D9] accent-[#E51E56]"
                        />
                      </td>
                      <td className="px-3 py-4">
                        <p className="font-semibold">{vendor.business_name}</p>
                        <p className="text-[12px] text-[#4A6B7C]">{vendor.email}</p>
                      </td>
                      <td className="px-3 py-4">{getTierLabel(vendor.tier)}</td>
                      <td className="px-3 py-4">
                        <Badge variant={vendor.status}>{vendor.status}</Badge>
                      </td>
                      <td className="px-3 py-4">
                        <p className="font-mono text-[12px]">{vendor.squad_account_id || "N/A"}</p>
                      </td>
                      <td className="px-3 py-4">{vendor.rc_number || "N/A"}</td>
                      <td className="px-3 py-4">{formatDate(vendor.created_at)}</td>
                      <td className="px-3 py-4 text-right">
                        <Button
                          variant="danger"
                          size="sm"
                          loading={deletingId === vendor.id}
                          leftIcon={<Trash2 className="h-3.5 w-3.5" />}
                          onClick={() => void deleteVendor(vendor.id, vendor.business_name)}
                        >
                          Delete
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </main>
  );
}
