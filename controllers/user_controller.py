from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.security import hash_password
from models.db_models import Follow, Post, User
from models.schemas import (
    FollowResponse,
    UserBase,
    UserProfilePrivateResponse,
    UserProfileResponse,
    UserUpdate,
)

_ProfileT = TypeVar("_ProfileT", UserProfileResponse, UserProfilePrivateResponse)


def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """Retrieve a paginated list of users ordered by ID."""
    stmt = select(User).order_by(User.id).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


def get_user_by_id(db: Session, user_id: int) -> User:
    """Retrieve a single user by ID or raise 404."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )
    return user


def _count_followers(db: Session, user_id: int) -> int:
    """Count followers for a given user."""
    stmt = select(func.count(Follow.id)).where(Follow.following_id == user_id)
    return int(db.scalar(stmt) or 0)


def _to_profile_response(
    db: Session,
    user_id: int,
    schema_cls: type[_ProfileT],
    *,
    include_email: bool = False,
) -> _ProfileT:
    """Build a public or private user profile response with activity counts."""
    user = get_user_by_id(db, user_id)
    posts_count = int(
        db.scalar(select(func.count(Post.id)).where(Post.author_id == user_id)) or 0
    )
    followers_count = _count_followers(db, user_id)
    following_count = int(
        db.scalar(select(func.count(Follow.id)).where(Follow.follower_id == user_id))
        or 0
    )
    payload: dict[str, object] = {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "posts_count": posts_count,
        "followers_count": followers_count,
        "following_count": following_count,
    }
    if include_email:
        payload["email"] = user.email
    return schema_cls.model_validate(payload)


def get_user_profile(db: Session, user_id: int) -> UserProfileResponse:
    """Retrieve a user's public profile with posts, followers, and following counts."""
    return _to_profile_response(db, user_id, UserProfileResponse)


def get_my_profile(db: Session, user_id: int) -> UserProfilePrivateResponse:
    """Retrieve the authenticated user's profile with email and activity counts."""
    return _to_profile_response(
        db, user_id, UserProfilePrivateResponse, include_email=True
    )


def _commit_and_refresh(db: Session, user: User) -> User:
    """Commit changes to the database, handling uniqueness conflicts."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        ) from exc
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user_id: int,
    user_data: UserUpdate | UserBase,
    *,
    current_user_id: int,
    exclude_unset: bool = True,
) -> User:
    """Update fields on the authenticated user's account."""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify another user",
        )
    user = get_user_by_id(db, user_id)
    updates = user_data.model_dump(exclude_unset=exclude_unset)
    if not updates:
        return user

    new_password = updates.pop("password", None)
    if isinstance(new_password, str):
        user.hashed_password = hash_password(new_password)

    for field, value in updates.items():
        setattr(user, field, value)
    return _commit_and_refresh(db, user)


def delete_user(db: Session, user_id: int, *, current_user_id: int) -> None:
    """Delete the authenticated user's account and associated follow edges."""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete another user",
        )
    user = get_user_by_id(db, user_id)
    db.execute(
        delete(Follow).where(
            (Follow.follower_id == user_id) | (Follow.following_id == user_id)
        )
    )
    db.delete(user)
    db.commit()


def follow_user(db: Session, follower_id: int, following_id: int) -> FollowResponse:
    """Create a follow relationship between two users."""
    if follower_id == following_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Users cannot follow themselves",
        )

    get_user_by_id(db, follower_id)
    get_user_by_id(db, following_id)

    follow = Follow(follower_id=follower_id, following_id=following_id)
    db.add(follow)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already following this account",
        ) from exc

    return FollowResponse(
        follower_id=follower_id,
        following_id=following_id,
        following=True,
        followers_count=_count_followers(db, following_id),
    )


def unfollow_user(
    db: Session, follower_id: int, following_id: int
) -> FollowResponse:
    """Remove an existing follow relationship between two users."""
    get_user_by_id(db, follower_id)
    get_user_by_id(db, following_id)

    stmt = select(Follow).where(
        Follow.follower_id == follower_id,
        Follow.following_id == following_id,
    )
    follow = db.scalar(stmt)
    if follow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Follow relationship not found",
        )

    db.delete(follow)
    db.commit()
    return FollowResponse(
        follower_id=follower_id,
        following_id=following_id,
        following=False,
        followers_count=_count_followers(db, following_id),
    )


def get_followers(
    db: Session, user_id: int, skip: int = 0, limit: int = 100
) -> list[User]:
    """List users who follow the specified user."""
    get_user_by_id(db, user_id)
    stmt = (
        select(User)
        .join(Follow, Follow.follower_id == User.id)
        .where(Follow.following_id == user_id)
        .order_by(Follow.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def get_following(
    db: Session, user_id: int, skip: int = 0, limit: int = 100
) -> list[User]:
    """List users followed by the specified user."""
    get_user_by_id(db, user_id)
    stmt = (
        select(User)
        .join(Follow, Follow.following_id == User.id)
        .where(Follow.follower_id == user_id)
        .order_by(Follow.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
