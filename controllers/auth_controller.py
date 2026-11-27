from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config.security import create_access_token, hash_password, verify_password
from models.db_models import User
from models.schemas import TokenResponse, UserRegister


def register_user(db: Session, user_data: UserRegister) -> User:
    """Register a new user with an Argon2-hashed password."""
    user_fields = user_data.model_dump(exclude={"password"})
    new_user = User(
        **user_fields,
        hashed_password=hash_password(user_data.password),
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        ) from exc
    db.refresh(new_user)
    return new_user


def authenticate_user(
    db: Session, username_or_email: str, password: str
) -> TokenResponse:
    """Verify credentials and issue a JWT bearer access token."""
    stmt = select(User).where(
        (User.username == username_or_email) | (User.email == username_or_email)
    )
    user = db.scalar(stmt)
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    access_token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=access_token)
