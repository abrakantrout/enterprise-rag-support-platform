import logging
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import jwt
from app.database.models import User, Role, Organization
from app.utilities.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)

logger = logging.getLogger(__name__)


def bootstrap_defaults(db: Session) -> tuple[Organization, dict[str, Role]]:
    """
    Bootstrap a default organization and roles if they do not exist in database.

    Args:
        db (Session): Database session.

    Returns:
        tuple[Organization, dict[str, Role]]: Seeded Org and Role map.
    """
    org = db.query(Organization).first()
    if not org:
        org = Organization(name="Default Enterprise")
        db.add(org)
        db.commit()
        db.refresh(org)

    roles = {}
    for name in ["Administrator", "Support Agent"]:
        role = db.query(Role).filter(Role.name == name).first()
        if not role:
            role = Role(name=name)
            db.add(role)
            db.commit()
            db.refresh(role)
        roles[name] = role

    return org, roles


def register_user(user_data: dict, db: Session) -> User:
    """
    Registers a new system user in the database.

    Args:
        user_data (dict): User attributes (email, password, names, role).
        db (Session): Database session.

    Returns:
        User: Created User record.
    """
    email = user_data.get("email")

    # Enforce uniqueness constraint
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address is already registered"
        )

    # Ensure defaults exist
    org, roles_map = bootstrap_defaults(db)

    role_name = user_data.get("role")
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = roles_map.get(role_name)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{role_name}' does not exist"
            )

    # Hash user credentials and save
    hashed = hash_password(user_data.get("password"))
    new_user = User(
        email=email,
        hashed_password=hashed,
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name"),
        role_id=role.id,
        organization_id=org.id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def authenticate_user(credentials: dict, db: Session) -> dict:
    """
    Verifies user credentials and generates JWT session tokens.

    Args:
        credentials (dict): Username and password dict.
        db (Session): Database session.

    Returns:
        dict: Generated session tokens payload.
    """
    email = credentials.get("username")
    password = credentials.get("password")

    user = db.query(User).filter(User.email == email, User.is_deleted == False).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token_payload = {"email": user.email, "role": user.role.name}

    access_token = create_access_token(data=token_payload)
    refresh_token = create_refresh_token(data=token_payload)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 1800,  # 30 minutes in seconds
        "refresh_token": refresh_token
    }


def refresh_user_token(refresh_token: str, db: Session) -> dict:
    """
    Validates a refresh token and generates a new session token pair.

    Args:
        refresh_token (str): JWT refresh token.
        db (Session): Database session.

    Returns:
        dict: Token refresh response.
    """
    try:
        payload = decode_token(refresh_token)
        email = payload.get("email")
        token_type = payload.get("type")

        if email is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user = db.query(User).filter(User.email == email, User.is_deleted == False).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    token_payload = {"email": user.email, "role": user.role.name}
    access_token = create_access_token(data=token_payload)
    new_refresh_token = create_refresh_token(data=token_payload)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 1800,
        "refresh_token": new_refresh_token
    }
