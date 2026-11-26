import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"

import { MetricsService } from "@/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { requirePermission } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/metrics")({
  component: Metrics,
  beforeLoad: ({ context }) =>
    requirePermission(context.queryClient, "metrics:read"),
  head: () => ({
    meta: [
      {
        title: "Metrics - FastAPI Template",
      },
    ],
  }),
})

function MetricCard({ title, value }: { title: string; value?: number }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-3xl font-bold">{value ?? "–"}</CardContent>
    </Card>
  )
}

function Metrics() {
  const { data: metrics } = useQuery({
    queryKey: ["metrics"],
    queryFn: async () => (await MetricsService.readMetrics()).data,
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Metrics</h1>
        <p className="text-muted-foreground">Overview of the application</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <MetricCard title="Users" value={metrics?.users_count} />
        <MetricCard title="Items" value={metrics?.items_count} />
      </div>
    </div>
  )
}
