"""Register user command — creates User + StaffMember in one transaction.

The handler does NOT commit — the caller (route) is responsible for calling
uow.commit() inside the `async with uow:` block.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from app.core.security import hash_password
from modules.iam.infrastructure.db.models import StaffMemberModel, UserModel
from modules.iam.infrastructure.db.repository import StaffMemberRepository, UserRepository
from shared.domain.exceptions import DuplicateResourceError
from shared.domain.ids import generate_uuid


async def register_user(
    *,
    user_repo: UserRepository,
    staff_repo: StaffMemberRepository,
    store_id: UUID,
    email: str,
    password: str,
    display_name: str,
) -> tuple[UUID, UUID]:
    """Create a new User + StaffMember.

    Returns
    -------
    (user_id, staff_member_id)

    Raises
    ------
    DuplicateResourceError : if email is already registered for this store.
    """
    existing = await user_repo.get_by_email(email=email)
    if existing is not None:
        raise DuplicateResourceError(f"User with email '{email}' already exists", code="DUPLICATE_RESOURCE")

    now = datetime.now(timezone.utc)
    user_id = generate_uuid()
    staff_member_id = generate_uuid()

    user = UserModel(
        user_id=user_id,
        email=email,
        password_hash=hash_password(password),
        status="ACTIVE",
        created_at=now,
        updated_at=now,
    )
    await user_repo.save(user)

    member = StaffMemberModel(
        staff_member_id=staff_member_id,
        store_id=store_id,
        user_id=user_id,
        display_name=display_name,
        status="ACTIVE",
        created_at=now,
    )
    await staff_repo.save(member)

    return user_id, staff_member_id