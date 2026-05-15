"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, LogIn } from "lucide-react";
import toast from "react-hot-toast";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { api } from "@/lib/api";
import { setActiveVendorId } from "@/lib/session";

export default function VendorLoginPage() {
  const router = useRouter();
  const [businessName, setBusinessName] = useState("");
  const [rcNumber, setRcNumber] = useState("");
  const [loading, setLoading] = useState(false);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!businessName.trim() || !rcNumber.trim()) {
      toast.error("Enter your business name and RC number");
      return;
    }

    setLoading(true);
    try {
      const vendor = await api.loginVendor({
        business_name: businessName.trim(),
        rc_number: rcNumber.trim(),
      });
      setActiveVendorId(vendor.id);
      toast.success(`Welcome, ${vendor.business_name}`);
      router.push("/vendor");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Vendor login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F8F9FA] p-6">
      <Card className="w-full max-w-md">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#0B3142] text-white">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-[22px] font-bold leading-tight text-[#0B3142]">Vendor Portal</h1>
            <p className="text-[13px] text-[#4A6B7C]">Sign in with your registered business details.</p>
          </div>
        </div>

        <form className="space-y-4" onSubmit={(event) => void submitLogin(event)}>
          <Input
            label="Business Name"
            value={businessName}
            onChange={(event) => setBusinessName(event.target.value)}
            placeholder="Registered business name"
          />
          <Input
            label="RC Number"
            value={rcNumber}
            onChange={(event) => setRcNumber(event.target.value)}
            placeholder="RC123456"
          />
          <Button className="w-full" size="lg" type="submit" loading={loading} leftIcon={<LogIn className="h-4 w-4" />}>
            Sign in
          </Button>
        </form>
      </Card>
    </main>
  );
}
