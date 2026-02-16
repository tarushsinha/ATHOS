from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, MeResponse, SignupRequest, TokenResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    existing_user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing_user is not None:
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already in use",
        ) from None

    db.refresh(user)
    token = create_access_token(user.user_id)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
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