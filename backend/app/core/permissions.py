"""Single source of truth for role-based access rules.

Authorization is always evaluated against the role stored on the current
database record, never against claims embedded in the access token, so role
changes apply to existing sessions immediately.
"""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"


class Permission(StrEnum):
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    METRICS_READ = "metrics:read"
    # Read/update/delete items owned by other users (former superuser behavior)
    ITEMS_MANAGE_ALL = "items:manage_all"
    UTILS_TEST_EMAIL = "utils:test_email"


# Reading and updating one's own profile and items needs no permission: every
# active, authenticated user can do it.
ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    # Admins keep every privilege the former superuser flag granted.
    UserRole.ADMIN: frozenset(Permission),
    UserRole.MANAGER: frozenset({Permission.USERS_READ, Permission.METRICS_READ}),
    UserRole.MEMBER: frozenset(),
}


def get_permissions(role: UserRole | str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[UserRole(role)]


def has_permission(role: UserRole | str, permission: Permission) -> bool:
    return permission in get_permissions(role)
