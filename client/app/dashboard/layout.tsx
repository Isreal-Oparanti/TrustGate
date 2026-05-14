import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#F8F9FA]">
      <Sidebar />
      <Topbar />
      <main className="px-5 py-8 lg:ml-60 lg:px-8">{children}</main>
    </div>
  );
}
