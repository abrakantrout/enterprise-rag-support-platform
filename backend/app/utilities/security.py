import logging
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from app.core.config import settings

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """
    Hashes a plain text password using bcrypt with standard salt generation.

    Args:
        password (str): The plain text password.

    Returns:
        str: The hashed password string.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain text password against a stored bcrypt hash.

    Args:
        plain_password (str): The plain text password to check.
        hashed_password (str): The stored hashed password.

    Returns:
        bool: True if password matches, False otherwise.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    Generates a signed JWT access token.

    Args:
        data (dict): The payload parameters to encode.
        expires_delta (timedelta, optional): Custom expiration duration.

    Returns:
        str: Signed JWT string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": int(expire.timestamp()), "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    Generates a signed JWT refresh token.

    Args:
        data (dict): The payload parameters to encode.
        expires_delta (timedelta, optional): Custom expiration duration.

    Returns:
        str: Signed JWT string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.refresh_token_expire_minutes)

    to_encode.update({"exp": int(expire.timestamp()), "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """
    Decodes and verifies a JWT token signature and expiration.

    Args:
        token (str): Signed JWT token string.

    Returns:
        dict: The decoded payload dictionary.

    Raises:
        jwt.PyJWTError: If signature is invalid or token is expired.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
