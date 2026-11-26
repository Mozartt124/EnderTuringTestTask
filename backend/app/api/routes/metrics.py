from fastapi import APIRouter, Depends
from sqlmodel import func, select

from app.api.deps import SessionDep, require_permission
from app.core.permissions import Permission
from app.models import Item, MetricsPublic, User

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get(
    "/",
    dependencies=[Depends(require_permission(Permission.METRICS_READ))],
)
def read_metrics(session: SessionDep) -> MetricsPublic:
    """
    Minimal metrics stub.
    """
    users_count = session.exec(select(func.count()).select_from(User)).one()
    items_count = session.exec(select(func.count()).select_from(Item)).one()
    return MetricsPublic(users_count=users_count, items_count=items_count)
