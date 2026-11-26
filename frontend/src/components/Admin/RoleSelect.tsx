import type { UserRole } from "@/client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: "Admin",
  manager: "Manager",
  member: "Member",
}

export const ROLES = Object.keys(ROLE_LABELS) as [UserRole, ...UserRole[]]

type RoleSelectProps = Omit<
  React.ComponentProps<typeof SelectTrigger>,
  "value" | "onChange"
> & {
  value: UserRole
  onChange: (value: UserRole) => void
}

// Used inside a <FormControl>, which passes the id and aria attributes that
// link the label to the trigger.
export function RoleSelect({ value, onChange, ...props }: RoleSelectProps) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as UserRole)}>
      <SelectTrigger className="w-full" {...props}>
        <SelectValue placeholder="Select a role" />
      </SelectTrigger>
      <SelectContent>
        {ROLES.map((role) => (
          <SelectItem key={role} value={role}>
            {ROLE_LABELS[role]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
