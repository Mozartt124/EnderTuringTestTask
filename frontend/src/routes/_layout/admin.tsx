import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import useAuth, { hasPermission, requirePermission } from "@/hooks/useAuth"

function getUsersQueryOptions() {
  return {
    queryFn: async () =>
      (await UsersService.readUsers({ query: { skip: 0, limit: 100 } })).data,
    queryKey: ["users"],
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: ({ context }) =>
    requirePermission(context.queryClient, "users:read"),
  head: () => ({
    meta: [
      {
        title: "Admin - FastAPI Template",
      },
    ],
  }),
})

function UsersTableContent({ canManage }: { canManage: boolean }) {
  const { user: currentUser } = useAuth()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())
  // Read-only viewers (Managers) get no edit/delete actions column.
  const visibleColumns = canManage
    ? columns
    : columns.filter((column) => column.id !== "actions")

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return <DataTable columns={visibleColumns} data={tableData} />
}

function UsersTable({ canManage }: { canManage: boolean }) {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent canManage={canManage} />
    </Suspense>
  )
}

function Admin() {
  const { user: currentUser } = useAuth()
  const canManage = hasPermission(currentUser, "users:manage")

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Users</h1>
          <p className="text-muted-foreground">
            {canManage
              ? "Manage user accounts and permissions"
              : "View user accounts"}
          </p>
        </div>
        {canManage && <AddUser />}
      </div>
      <UsersTable canManage={canManage} />
    </div>
  )
}
