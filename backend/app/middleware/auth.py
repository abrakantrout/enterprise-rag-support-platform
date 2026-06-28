import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database.models import User
from app.utilities.security import decode_token

logger = logging.getLogger(__name__)

# Standard OAuth2 bearer schema extracting token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency that decodes the JWT access token and retrieves the current user
    from the database.

    Raises:
        HTTPException: 401 Unauthorized if the credentials fail validation.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = decode_token(token)
        email: str = payload.get("email")
        token_type: str = payload.get("type")

        if email is None or token_type != "access":
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email, User.is_deleted == False).first()
    if user is None:
        raise credentials_exception

    return user


class RoleChecker:
    """
    Route guard dependency that restricts endpoint access based on user roles.
    """

    def __init__(self, allowed_roles: list[str]):
        """
        Args:
            allowed_roles (list[str]): List of role names permitted to access the route.
        """
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        # Resolve the role name from the user relationship
        role_name = current_user.role.name if current_user.role else None

        if role_name not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions block access to this resource"
            )
        return current_user
