from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ItemBase(BaseModel):
    """Shared fields and validation rules for Item schemas."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price: float = Field(..., ge=0)
    is_active: bool = True

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ItemCreate(ItemBase):
    """Schema for creating or replacing an item."""


class ItemUpdate(BaseModel):
    """Schema for partially updating an existing item."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    price: float | None = Field(default=None, ge=0)
    is_active: bool | None = None

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("name", "price", "is_active")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        """Disallow explicit null for non-nullable database columns."""
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class ItemResponse(ItemBase):
    """Schema returned in API responses."""

    id: int

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class UserPublicBase(BaseModel):
    """Publicly visible fields and validation rules for social media User schemas."""

    username: str = Field(..., min_length=1, max_length=50)
    display_name: str | None = Field(default=None, max_length=80)
    bio: str | None = Field(default=None, max_length=300)
    is_active: bool = True

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class UserBase(UserPublicBase):
    """Shared fields including private email for account input schemas."""

    email: EmailStr = Field(..., max_length=100)


class UserRegister(UserBase):
    """Schema for registering a new user account."""

    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Schema for partially updating an existing social media user."""

    username: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=100)
    display_name: str | None = Field(default=None, max_length=80)
    bio: str | None = Field(default=None, max_length=300)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("username", "email", "password", "is_active")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        """Disallow explicit null for non-nullable database columns."""
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class UserPublicResponse(UserPublicBase):
    """Public schema returned in API responses (excludes email)."""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class UserPrivateResponse(UserPublicResponse):
    """Private schema returned only to the account owner (includes email)."""

    email: EmailStr

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class UserProfileResponse(UserPublicResponse):
    """Public user profile schema including social activity counts."""

    posts_count: int = 0
    followers_count: int = 0
    following_count: int = 0


class UserProfilePrivateResponse(UserPrivateResponse):
    """Private user profile schema for /users/me including email and counts."""

    posts_count: int = 0
    followers_count: int = 0
    following_count: int = 0


class TokenResponse(BaseModel):
    """JWT access token response schema."""

    access_token: str
    token_type: str = "bearer"


class PostBase(BaseModel):
    """Shared fields and validation rules for Post schemas."""

    content: str = Field(..., min_length=1, max_length=5000)
    image_url: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class PostCreate(PostBase):
    """Schema for creating a new post as the authenticated user."""


class PostUpdate(BaseModel):
    """Schema for partially updating an existing post."""

    content: str | None = Field(default=None, min_length=1, max_length=5000)
    image_url: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    @field_validator("content")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        """Disallow explicit null for non-nullable content column."""
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class PostResponse(BaseModel):
    """Schema returned in API responses for a post."""

    id: int
    author_id: int
    content: str
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    likes_count: int = 0
    comments_count: int = 0

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class CommentBase(BaseModel):
    """Shared fields and validation rules for Comment schemas."""

    content: str = Field(..., min_length=1, max_length=1000)

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class CommentCreate(CommentBase):
    """Schema for creating a comment as the authenticated user."""


class CommentUpdate(CommentBase):
    """Schema for updating a comment."""


class CommentResponse(BaseModel):
    """Schema returned in API responses for a comment."""

    id: int
    post_id: int
    author_id: int
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class LikeResponse(BaseModel):
    """Schema returned after liking or unliking a post."""

    post_id: int
    user_id: int
    liked: bool
    likes_count: int


class FollowResponse(BaseModel):
    """Schema returned after following or unfollowing a user."""

    follower_id: int
    following_id: int
    following: bool
    followers_count: int
