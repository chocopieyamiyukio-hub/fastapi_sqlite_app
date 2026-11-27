from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from controllers.user_controller import get_user_by_id
from models.db_models import Comment, Follow, Post, PostLike, User
from models.schemas import (
    CommentCreate,
    CommentUpdate,
    LikeResponse,
    PostBase,
    PostCreate,
    PostResponse,
    PostUpdate,
)


def _count_by_post(
    db: Session, model: type[PostLike] | type[Comment], post_ids: list[int]
) -> dict[int, int]:
    """Batch count related rows grouped by post_id to avoid N+1 queries."""
    if not post_ids:
        return {}
    stmt = (
        select(model.post_id, func.count(model.id))
        .where(model.post_id.in_(post_ids))
        .group_by(model.post_id)
    )
    return {int(post_id): int(total) for post_id, total in db.execute(stmt).all()}


def _serialize_posts(db: Session, posts: list[Post]) -> list[PostResponse]:
    """Convert ORM Post objects into PostResponse models with engagement counts."""
    post_ids = [post.id for post in posts]
    likes_map = _count_by_post(db, PostLike, post_ids)
    comments_map = _count_by_post(db, Comment, post_ids)
    return [
        PostResponse(
            id=post.id,
            author_id=post.author_id,
            content=post.content,
            image_url=post.image_url,
            created_at=post.created_at,
            updated_at=post.updated_at,
            likes_count=likes_map.get(post.id, 0),
            comments_count=comments_map.get(post.id, 0),
        )
        for post in posts
    ]


def _serialize_post(db: Session, post: Post) -> PostResponse:
    """Convert a single ORM Post object into PostResponse."""
    return _serialize_posts(db, [post])[0]


def get_post_by_id(db: Session, post_id: int) -> Post:
    """Retrieve a single post ORM model by ID or raise 404."""
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with id {post_id} not found",
        )
    return post


def get_post_response(db: Session, post_id: int) -> PostResponse:
    """Retrieve a single post with likes and comments counts."""
    post = get_post_by_id(db, post_id)
    return _serialize_post(db, post)


def get_posts(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    author_id: int | None = None,
) -> list[PostResponse]:
    """List posts newest-first, optionally filtered by author."""
    stmt = select(Post)
    if author_id is not None:
        get_user_by_id(db, author_id)
        stmt = stmt.where(Post.author_id == author_id)
    stmt = stmt.order_by(Post.created_at.desc(), Post.id.desc()).offset(skip).limit(limit)
    posts = list(db.scalars(stmt).all())
    return _serialize_posts(db, posts)


def get_feed(
    db: Session, user_id: int, skip: int = 0, limit: int = 100
) -> list[PostResponse]:
    """List posts from accounts followed by user_id plus their own posts."""
    get_user_by_id(db, user_id)
    following_subquery = select(Follow.following_id).where(
        Follow.follower_id == user_id
    )
    stmt = (
        select(Post)
        .where((Post.author_id == user_id) | (Post.author_id.in_(following_subquery)))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset(skip)
        .limit(limit)
    )
    posts = list(db.scalars(stmt).all())
    return _serialize_posts(db, posts)


def create_post(db: Session, author_id: int, post_data: PostCreate) -> PostResponse:
    """Create and persist a new post for the authenticated author."""
    get_user_by_id(db, author_id)
    new_post = Post(author_id=author_id, **post_data.model_dump())
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return _serialize_post(db, new_post)


def update_post(
    db: Session,
    post_id: int,
    post_data: PostUpdate | PostBase,
    *,
    current_user_id: int,
    exclude_unset: bool = True,
) -> PostResponse:
    """Update fields on an existing post owned by current_user_id."""
    post = get_post_by_id(db, post_id)
    if post.author_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify another user's post",
        )
    updates = post_data.model_dump(exclude_unset=exclude_unset)
    if not updates:
        return _serialize_post(db, post)

    for field, value in updates.items():
        setattr(post, field, value)
    post.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(post)
    return _serialize_post(db, post)


def delete_post(db: Session, post_id: int, *, current_user_id: int) -> None:
    """Delete a post owned by current_user_id."""
    post = get_post_by_id(db, post_id)
    if post.author_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete another user's post",
        )
    db.delete(post)
    db.commit()


def _count_post_likes(db: Session, post_id: int) -> int:
    """Count total likes on a post."""
    stmt = select(func.count(PostLike.id)).where(PostLike.post_id == post_id)
    return int(db.scalar(stmt) or 0)


def like_post(db: Session, post_id: int, user_id: int) -> LikeResponse:
    """Like a post on behalf of the authenticated user."""
    get_post_by_id(db, post_id)
    get_user_by_id(db, user_id)

    like = PostLike(post_id=post_id, user_id=user_id)
    db.add(like)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has already liked this post",
        ) from exc

    return LikeResponse(
        post_id=post_id,
        user_id=user_id,
        liked=True,
        likes_count=_count_post_likes(db, post_id),
    )


def unlike_post(db: Session, post_id: int, user_id: int) -> LikeResponse:
    """Remove the authenticated user's like from a post."""
    get_post_by_id(db, post_id)
    get_user_by_id(db, user_id)

    stmt = select(PostLike).where(
        PostLike.post_id == post_id,
        PostLike.user_id == user_id,
    )
    like = db.scalar(stmt)
    if like is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Like not found for this user and post",
        )

    db.delete(like)
    db.commit()
    return LikeResponse(
        post_id=post_id,
        user_id=user_id,
        liked=False,
        likes_count=_count_post_likes(db, post_id),
    )


def get_post_likes(
    db: Session, post_id: int, skip: int = 0, limit: int = 100
) -> list[User]:
    """List users who liked the specified post."""
    get_post_by_id(db, post_id)
    stmt = (
        select(User)
        .join(PostLike, PostLike.user_id == User.id)
        .where(PostLike.post_id == post_id)
        .order_by(PostLike.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def get_comment_by_id(db: Session, comment_id: int) -> Comment:
    """Retrieve a single comment by ID or raise 404."""
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment with id {comment_id} not found",
        )
    return comment


def create_comment(
    db: Session, post_id: int, author_id: int, comment_data: CommentCreate
) -> Comment:
    """Create a comment on an existing post for the authenticated author."""
    get_post_by_id(db, post_id)
    get_user_by_id(db, author_id)

    new_comment = Comment(
        post_id=post_id, author_id=author_id, **comment_data.model_dump()
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment


def get_comments_for_post(
    db: Session, post_id: int, skip: int = 0, limit: int = 100
) -> list[Comment]:
    """List comments for a post ordered chronologically."""
    get_post_by_id(db, post_id)
    stmt = (
        select(Comment)
        .where(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def update_comment(
    db: Session,
    comment_id: int,
    comment_data: CommentUpdate,
    *,
    current_user_id: int,
) -> Comment:
    """Update a comment owned by current_user_id."""
    comment = get_comment_by_id(db, comment_id)
    if comment.author_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify another user's comment",
        )
    comment.content = comment_data.content
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(
    db: Session, comment_id: int, *, current_user_id: int
) -> None:
    """Delete a comment owned by current_user_id."""
    comment = get_comment_by_id(db, comment_id)
    if comment.author_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete another user's comment",
        )
    db.delete(comment)
    db.commit()
