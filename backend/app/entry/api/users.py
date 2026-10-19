"""The signed-in reader's own account."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.db.user import User
from app.entry.api.deps import CurrentUser, SessionDep
from app.features.audience import service
from app.features.audience.model import Message, UserPublic, UserUpdateMe

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> User:
    """
    Update own user.
    """
    if user_in.email:
        existing_user = service.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    return service.update_profile(
        session=session, db_user=current_user, changes=user_in
    )


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> User:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Message:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    service.delete_account(session=session, db_user=current_user)
    return Message(message="User deleted successfully")
