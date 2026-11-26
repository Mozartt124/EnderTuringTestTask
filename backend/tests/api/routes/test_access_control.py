import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.permissions import UserRole
from app.models import ItemCreate, User, UserCreate
from tests.utils.user import create_random_user, user_authentication_headers
from tests.utils.utils import random_email, random_lower_string

API = settings.API_V1_STR


def create_user_with_headers(
    client: TestClient, db: Session, role: UserRole
) -> tuple[User, dict[str, str]]:
    email, password = random_email(), random_lower_string()
    user = crud.create_user(
        session=db, user_create=UserCreate(email=email, password=password, role=role)
    )
    headers = user_authentication_headers(client=client, email=email, password=password)
    return user, headers


@pytest.mark.parametrize(
    ("role", "expected_permissions"),
    [
        (
            UserRole.ADMIN,
            [
                "items:manage_all",
                "metrics:read",
                "users:manage",
                "users:read",
                "utils:test_email",
            ],
        ),
        (UserRole.MANAGER, ["metrics:read", "users:read"]),
        (UserRole.MEMBER, []),
    ],
)
def test_read_me_exposes_role_and_permissions(
    client: TestClient, db: Session, role: UserRole, expected_permissions: list[str]
) -> None:
    _, headers = create_user_with_headers(client, db, role)
    r = client.get(f"{API}/users/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == role.value
    assert r.json()["permissions"] == expected_permissions


@pytest.mark.parametrize(
    ("role", "can_read", "can_manage"),
    [
        (UserRole.ADMIN, True, True),
        (UserRole.MANAGER, True, False),
        (UserRole.MEMBER, False, False),
    ],
)
def test_user_and_metrics_access_by_role(
    client: TestClient, db: Session, role: UserRole, can_read: bool, can_manage: bool
) -> None:
    me, headers = create_user_with_headers(client, db, role)
    other = create_random_user(db)
    read_status = 200 if can_read else 403

    # Every role can read its own record by id (template behavior).
    r = client.get(f"{API}/users/{me.id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == str(me.id)

    assert client.get(f"{API}/users/", headers=headers).status_code == read_status
    r = client.get(f"{API}/users/{other.id}", headers=headers)
    assert r.status_code == read_status
    assert client.get(f"{API}/metrics/", headers=headers).status_code == read_status

    if can_manage:
        return
    new_user = {"email": random_email(), "password": random_lower_string()}
    r = client.post(f"{API}/users/", headers=headers, json=new_user)
    assert r.status_code == 403
    r = client.patch(f"{API}/users/{other.id}", headers=headers, json={"role": "admin"})
    assert r.status_code == 403
    r = client.delete(f"{API}/users/{other.id}", headers=headers)
    assert r.status_code == 403
    db.refresh(other)
    assert other.role == UserRole.MEMBER

    # A forbidden action does not invalidate the session.
    assert client.get(f"{API}/users/me", headers=headers).status_code == 200


def test_admin_can_set_role(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user = create_random_user(db)
    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"role": "manager"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "manager"

    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"role": "owner"},
    )
    assert r.status_code == 422


def test_admin_update_omitted_keeps_and_null_rejects_role_and_active(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user, _ = create_user_with_headers(client, db, UserRole.MANAGER)

    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"full_name": "Renamed"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "manager"
    assert r.json()["is_active"] is True

    for field in ("role", "is_active"):
        r = client.patch(
            f"{API}/users/{user.id}",
            headers=superuser_token_headers,
            json={field: None},
        )
        assert r.status_code == 422, field

    db.refresh(user)
    assert user.full_name == "Renamed"
    assert user.role == UserRole.MANAGER
    assert user.is_active is True


def test_signup_cannot_set_role_or_active_status(
    client: TestClient, db: Session
) -> None:
    email = random_email()
    data = {
        "email": email,
        "password": random_lower_string(),
        "role": "admin",
        "is_active": False,
    }
    r = client.post(f"{API}/users/signup", json=data)
    assert r.status_code == 200
    assert r.json()["role"] == "member"
    assert r.json()["is_active"] is True
    user = crud.get_user_by_email(session=db, email=email)
    assert user
    assert user.role == UserRole.MEMBER


def test_update_me_cannot_change_role_or_active_status(
    client: TestClient, db: Session
) -> None:
    user, headers = create_user_with_headers(client, db, UserRole.MEMBER)
    r = client.patch(
        f"{API}/users/me",
        headers=headers,
        json={"full_name": "Changed", "role": "admin", "is_active": False},
    )
    assert r.status_code == 200
    db.refresh(user)
    assert user.full_name == "Changed"
    assert user.role == UserRole.MEMBER
    assert user.is_active is True


def test_role_change_applies_to_existing_session(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user, headers = create_user_with_headers(client, db, UserRole.MEMBER)
    assert client.get(f"{API}/metrics/", headers=headers).status_code == 403

    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"role": "manager"},
    )
    assert r.status_code == 200
    assert client.get(f"{API}/metrics/", headers=headers).status_code == 200

    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"role": "member"},
    )
    assert r.status_code == 200
    assert client.get(f"{API}/metrics/", headers=headers).status_code == 403


def test_deactivation_invalidates_existing_session(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user, headers = create_user_with_headers(client, db, UserRole.MANAGER)
    assert client.get(f"{API}/users/me", headers=headers).status_code == 200

    r = client.patch(
        f"{API}/users/{user.id}",
        headers=superuser_token_headers,
        json={"is_active": False},
    )
    assert r.status_code == 200
    r = client.get(f"{API}/users/", headers=headers)
    assert r.status_code == 401
    assert r.json()["detail"] == "Inactive user"


def test_invalid_token_returns_401(client: TestClient) -> None:
    r = client.get(
        f"{API}/users/me", headers={"Authorization": "Bearer not-a-valid-token"}
    )
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_manager_cannot_access_other_users_items(
    client: TestClient, db: Session
) -> None:
    owner = create_random_user(db)
    item = crud.create_item(
        session=db, item_in=ItemCreate(title="private"), owner_id=owner.id
    )
    _, headers = create_user_with_headers(client, db, UserRole.MANAGER)

    assert client.get(f"{API}/items/{item.id}", headers=headers).status_code == 403
    r = client.get(f"{API}/items/", headers=headers)
    assert r.status_code == 200
    assert r.json()["count"] == 0
