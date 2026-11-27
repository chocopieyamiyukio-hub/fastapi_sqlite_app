from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from config.database import get_db
from config.security import get_current_user
from controllers import auth_controller
from models.db_models import User
from models.schemas import TokenResponse, UserRegister, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db),
) -> User:
    """Register a new user account."""
    return auth_controller.register_user(db=db, user_data=user_data)


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username or email and password to obtain a JWT token."""
    return auth_controller.authenticate_user(
        db=db,
        username_or_email=form_data.username,
        password=form_data.password,
    )


@router.get("/me", response_model=UserResponse)
def read_auth_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the currently authenticated user."""
    return current_user
