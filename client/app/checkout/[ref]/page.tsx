import Link from "next/link";
import { CheckCircle, CreditCard } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

export default function MockCheckoutPage({ params }: { params: { ref: string } }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F8F9FA] px-5 py-10">
      <Card className="w-full max-w-lg text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[#E6F7F1] text-[#0D9B68]">
          <CreditCard className="h-7 w-7" />
        </div>
        <h1 className="mt-5 text-[24px] font-bold text-[#0B3142]">Mock Payment Checkout</h1>
        <p className="mt-2 text-[13px] text-[#4A6B7C]">
          This local checkout page is shown because Squad mock mode is enabled.
        </p>

        <div className="mt-6 rounded-lg border border-[#E5E9ED] bg-[#F8F9FA] p-4 text-left">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[#8FA3AF]">Transaction reference</p>
          <p className="mt-1 break-all font-mono text-[13px] text-[#0B3142]">{params.ref}</p>
        </div>

        <div className="mt-6 rounded-lg bg-[#E6F7F1] p-4 text-left">
          <div className="flex items-start gap-2">
            <CheckCircle className="mt-0.5 h-4 w-4 text-[#0D9B68]" />
            <p className="text-[13px] text-[#0B3142]">
              In live mode, Squad returns a hosted checkout URL. In mock mode, use this page to confirm that payment
              initiation generated a usable link.
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Link href="/dashboard/operations">
            <Button>Back to Operations</Button>
          </Link>
          <Link href="/dashboard/transactions">
            <Button variant="secondary">View Transactions</Button>
          </Link>
        </div>
      </Card>
    </main>
  );
}
