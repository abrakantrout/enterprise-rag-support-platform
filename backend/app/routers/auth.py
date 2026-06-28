from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import User
from app.middleware.auth import get_current_user, oauth2_scheme
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["User Authentication"])


# --- Schemas ---

class UserRegisterSchema(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    first_name: str = Field(..., description="User first name")
    last_name: str = Field(..., description="User last name")
    role: str = Field("Support Agent", description="Assigned role: Administrator or Support Agent")


class TokenResponseSchema(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str


class TokenRefreshRequestSchema(BaseModel):
    refresh_token: str


class UserProfileResponseSchema(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    organization_id: str


# --- Endpoints ---

@router.post("/register", response_model=UserProfileResponseSchema, status_code=status.HTTP_201_CREATED)
def register(
    schema: UserRegisterSchema,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme)
):
    """
    Registers a new user in the database.

    For bootstrapping: If no users exist, the first user can register without credentials.
    Subsequent user registrations require a valid Administrator access token.
    """
    user_count = db.query(User).count()

    if user_count > 0:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials required"
            )
        # Manually validate current user has Administrator privileges
        current_user = get_current_user(token=token, db=db)
        role_name = current_user.role.name if current_user.role else None
        if role_name != "Administrator":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Administrators can register new users"
            )

    new_user = auth_service.register_user(schema.model_dump(), db)
    role_name = new_user.role.name if new_user.role else "Support Agent"

    return {
        "id": new_user.id,
        "email": new_user.email,
        "first_name": new_user.first_name,
        "last_name": new_user.last_name,
        "role": role_name,
        "organization_id": new_user.organization_id
    }


@router.post("/login", response_model=TokenResponseSchema)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Verifies user credentials and returns signed JWT access and refresh tokens.
    """
    credentials = {
        "username": form_data.username,
        "password": form_data.password
    }
    return auth_service.authenticate_user(credentials, db)


@router.post("/refresh", response_model=TokenResponseSchema)
def refresh(
    schema: TokenRefreshRequestSchema,
    db: Session = Depends(get_db)
):
    """
    Exchanges a valid refresh token for a new access/refresh token pair.
    """
    return auth_service.refresh_user_token(schema.refresh_token, db)


@router.post("/logout")
def logout():
    """
    Logs out the user by discarding the current session tokens.
    Managed client-side by discarding the JWT payloads.
    """
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserProfileResponseSchema)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the user profile details for the currently authenticated session.
    """
    role_name = current_user.role.name if current_user.role else "Support Agent"
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": role_name,
        "organization_id": current_user.organization_id
    }
