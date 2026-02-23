import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, MeResponse, SignupRequest, TokenResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])
logger = logging.getLogger("athos.domain")


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    existing_user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing_user is not None:
        logger.info(
            "domain_event event=signup_failed reason=email_conflict request_id=%s",
            getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already in use",
        )

    user = User(
        email=email,
        name=payload.name.strip(),
        birth_year=payload.birth_year,
        birth_month=payload.birth_month,
        password_hash=hash_password(payload.password),
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info(
            "domain_event event=signup_failed reason=integrity_error request_id=%s",
            getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already in use",
        ) from None

    db.refresh(user)
    logger.info(
        "domain_event event=signup_success user_id=%s request_id=%s",
        user.user_id,
        getattr(request.state, "request_id", None),
    )
    token = create_access_token(user.user_id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        logger.info(
            "domain_event event=login_failed reason=invalid_credentials request_id=%s",
            getattr(request.state, "request_id", None),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    logger.info(
        "domain_event event=login_success user_id=%s request_id=%s",
        user.user_id,
        getattr(request.state, "request_id", None),
    )
    token = create_access_token(user.user_id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        user_id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        birth_year=current_user.birth_year,
        birth_month=current_user.birth_month,
    )
