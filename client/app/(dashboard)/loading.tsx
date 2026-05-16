import { Card } from "@/components/ui/Card";

export default function DashboardLoading() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="h-7 w-56 rounded skeleton" />
        <div className="h-4 w-80 max-w-full rounded skeleton" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <Card key={index}>
            <div className="h-4 w-24 rounded skeleton" />
            <div className="mt-4 h-8 w-20 rounded skeleton" />
            <div className="mt-3 h-3 w-32 rounded skeleton" />
          </Card>
        ))}
      </div>
      <Card>
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="grid gap-3 sm:grid-cols-[140px_1fr_120px]">
              <div className="h-4 rounded skeleton" />
              <div className="h-4 rounded skeleton" />
              <div className="h-4 rounded skeleton" />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
