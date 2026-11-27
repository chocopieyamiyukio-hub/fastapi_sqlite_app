from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from config.database import get_db
from config.security import get_current_user
from controllers import post_controller
from models.db_models import Comment, User
from models.schemas import (
    CommentCreate,
    CommentResponse,
    CommentUpdate,
    LikeResponse,
    PostBase,
    PostCreate,
    PostResponse,
    PostUpdate,
    UserPublicResponse,
)

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.post(
    "/",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_post(
    post_data: PostCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> PostResponse:
    """Create a new post as the authenticated user."""
    return post_controller.create_post(
        db=db, author_id=current_user.id, post_data=post_data
    )


@router.get("/", response_model=list[PostResponse])
def read_posts(
    author_id: int | None = Query(default=None, ge=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[PostResponse]:
    """List posts newest-first with optional author filter."""
    return post_controller.get_posts(
        db=db, skip=skip, limit=limit, author_id=author_id
    )


@router.get("/{post_id}", response_model=PostResponse)
def read_post(
    post_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> PostResponse:
    """Get a single post by ID."""
    return post_controller.get_post_response(db=db, post_id=post_id)


@router.patch("/{post_id}", response_model=PostResponse)
def patch_post(
    post_data: PostUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    post_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> PostResponse:
    """Partially update an existing post owned by the authenticated user."""
    return post_controller.update_post(
        db=db,
        post_id=post_id,
        post_data=post_data,
        current_user_id=current_user.id,
        exclude_unset=True,
    )


@router.put("/{post_id}", response_model=PostResponse)
def replace_post(
    post_data: PostBase,
    current_user: Annotated[User, Depends(get_current_user)],
    post_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> PostResponse:
    """Replace content and image_url of a post owned by the authenticated user."""
    return post_controller.update_post(
        db=db,
        post_id=post_id,
        post_data=post_data,
        current_user_id=current_user.id,
        exclude_unset=False,
    )


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    current_user: Annotated[User, Depends(get_current_user)],
    post_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> None:
    """Delete a post owned by the authenticated user."""
    post_controller.delete_post(
        db=db, post_id=post_id, current_user_id=current_user.id
    )


@router.post("/{post_id}/like", response_model=LikeResponse)
def like_post(
    current_user: Annotated[User, Depends(get_current_user)],
    post_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> LikeResponse:
    """Like a post as the authenticated user."""
    return post_controller.like_post(
        db=db, post_id=post_id, user_id=current_user.id
    )


@router.delete("/{post_id}/like", response_model=LikeResponse)
def unlike_post(
    current_user: Annotated[User, Depends(get_current_user)],
    post_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> LikeResponse:
    """Remove the authenticated user's like from a post."""
    return post_controller.unlike_post(
        db=db, post_id=post_id, user_id=current_user.id
    )


@router.get("/{post_id}/likes", response_model=list[UserPublicResponse])
def read_post_likes(
    post_id: int = Path(..., ge=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[User]:
    """List users who liked a post."""
    return post_controller.get_post_likes(
        db=db, post_id=post_id, skip=skip, limit=limit
    )


@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    comment_data: CommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    post_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> Comment:
    """Add a comment to a post as the authenticated user."""
    return post_controller.create_comment(
        db=db,
        post_id=post_id,
        author_id=current_user.id,
        comment_data=comment_data,
    )


@router.get("/{post_id}/comments", response_model=list[CommentResponse])
def read_comments(
    post_id: int = Path(..., ge=1),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Comment]:
    """List comments on a post."""
    return post_controller.get_comments_for_post(
        db=db, post_id=post_id, skip=skip, limit=limit
    )


@router.patch("/comments/{comment_id}", response_model=CommentResponse)
def patch_comment(
    comment_data: CommentUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    comment_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> Comment:
    """Update a comment owned by the authenticated user."""
    return post_controller.update_comment(
        db=db,
        comment_id=comment_id,
        comment_data=comment_data,
        current_user_id=current_user.id,
    )


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    current_user: Annotated[User, Depends(get_current_user)],
    comment_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> None:
    """Delete a comment owned by the authenticated user."""
    post_controller.delete_comment(
        db=db, comment_id=comment_id, current_user_id=current_user.id
    )
