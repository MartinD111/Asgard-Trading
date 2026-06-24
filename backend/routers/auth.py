import time
import collections
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import timedelta
from db.database import get_db
from pydantic import BaseModel
from services.auth_service import (
    verify_password, create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES, verify_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ─── Login rate-limiter (in-memory, per-IP) ───────────────────────────────────
# Max 10 attempts per 60 seconds per client IP. Resets on each window expiry.
_RATE_WINDOW = 60.0
_RATE_MAX = 10
_login_attempts: dict[str, list[float]] = collections.defaultdict(list)


def _check_login_rate(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - _RATE_WINDOW
    attempts = [t for t in _login_attempts[ip] if t > window_start]
    _login_attempts[ip] = attempts
    if len(attempts) >= _RATE_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {_RATE_WINDOW:.0f} seconds.",
        )
    _login_attempts[ip].append(now)


# ─── Schemas ──────────────────────────────────────────────────────────────────

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: str
    username: str
    is_admin: bool
    avatar_id: str


# ─── Auth dependencies ────────────────────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    result = await db.execute(
        text("SELECT id, username, is_admin, avatar_id FROM users WHERE username = :u"),
        {"u": username},
    )
    user = result.fetchone()
    if user is None:
        raise credentials_exception
    return dict(user._mapping)


async def get_current_admin(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    _check_login_rate(request)
    result = await db.execute(
        text("SELECT id, username, password_hash, is_admin, avatar_id FROM users WHERE username = :u"),
        {"u": form_data.username},
    )
    user = result.fetchone()
    if not user or not verify_password(form_data.password, user._mapping["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user._mapping["username"], "is_admin": user._mapping["is_admin"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}



@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user["id"]),
        username=current_user["username"],
        is_admin=current_user["is_admin"],
        avatar_id=current_user["avatar_id"],
    )
