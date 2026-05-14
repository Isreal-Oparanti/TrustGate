"use client";

import { useRouter } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

export default function LoginPage() {
  const router = useRouter();

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F8F9FA] p-6">
      <Card className="w-full max-w-md">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#E51E56] text-white">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-[22px] font-bold leading-tight text-[#0B3142]">TrustGate</h1>
            <p className="text-[13px] text-[#4A6B7C]">Compliance officer access</p>
          </div>
        </div>

        <div className="space-y-4">
          <Input label="Email" type="email" defaultValue="compliance@squadco.com" />
          <Input label="Password" type="password" defaultValue="trustgate-demo" />
          <Button className="w-full" size="lg" onClick={() => router.push("/dashboard")}>
            Sign in
          </Button>
        </div>
      </Card>
    </main>
  );
}
