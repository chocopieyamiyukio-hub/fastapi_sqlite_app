from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from config.database import get_db
from config.security import get_current_user
from controllers import post_controller, user_controller
from models.db_models import User
from models.schemas import (
    FollowResponse,
    PostResponse,
    UserBase,
    UserProfileResponse,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=list[UserResponse])
def read_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[User]:
    """List users with pagination."""
    return user_controller.get_users(db=db, skip=skip, limit=limit)


@router.get("/me", response_model=UserProfileResponse)
def read_my_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Get the authenticated user's profile with activity counts."""
    return user_controller.get_user_profile(db=db, user_id=current_user.id)


@router.get("/me/feed", response_model=list[PostResponse])
def read_my_feed(
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[PostResponse]:
    """Get personalized feed for the authenticated user."""
    return post_controller.get_feed(
        db=db, user_id=current_user.id, skip=skip, limit=limit
    )


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> User:
    """Get a single user by ID."""
    return user_controller.get_user_by_id(db=db, user_id=user_id)


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
def read_user_profile(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    """Get a user's profile with posts, followers, and following counts."""
    return user_controller.get_user_profile(db=db, user_id=user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def patch_user(
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> User:
    """Partially update the authenticated user's own account."""
    return user_controller.update_user(
        db=db,
        user_id=user_id,
        user_data=user_data,
        current_user_id=current_user.id,
        exclude_unset=True,
    )


@router.put("/{user_id}", response_model=UserResponse)
def replace_user(
    user_data: UserBase,
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> User:
    """Replace profile fields on the authenticated user's own account."""
    return user_controller.update_user(
        db=db,
        user_id=user_id,
        user_data=user_data,
        current_user_id=current_user.id,
        exclude_unset=False,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> None:
    """Delete the authenticated user's own account."""
    user_controller.delete_user(
        db=db, user_id=user_id, current_user_id=current_user.id
    )


@router.post("/{user_id}/follow", response_model=FollowResponse)
def follow_user(
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> FollowResponse:
    """Follow a target user as the authenticated user."""
    return user_controller.follow_user(
        db=db, follower_id=current_user.id, following_id=user_id
    )


@router.delete("/{user_id}/follow", response_model=FollowResponse)
def unfollow_user(
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> FollowResponse:
    """Unfollow a target user as the authenticated user."""
    return user_controller.unfollow_user(
        db=db, follower_id=current_user.id, following_id=user_id
    )


@router.get("/{user_id}/followers", response_model=list[UserResponse])
def read_followers(
    user_id: int = Path(..., ge=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[User]:
    """List followers of a user."""
    return user_controller.get_followers(db=db, user_id=user_id, skip=skip, limit=limit)


@router.get("/{user_id}/following", response_model=list[UserResponse])
def read_following(
    user_id: int = Path(..., ge=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[User]:
    """List accounts followed by a user."""
    return user_controller.get_following(db=db, user_id=user_id, skip=skip, limit=limit)
