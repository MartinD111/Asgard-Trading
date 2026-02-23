from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import timedelta
from db.database import get_db
from pydantic import BaseModel
from services.auth_service import verify_password, create_access_token, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES, verify_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    username: str
    is_admin: bool
    avatar_id: str

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
    
    result = await db.execute(text("SELECT id, username, is_admin, avatar_id FROM users WHERE username = :u"), {"u": username})
    user = result.fetchone()
    if user is None:
        raise credentials_exception
    return dict(user._mapping)

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT id, username, password_hash, is_admin, avatar_id FROM users WHERE username = :u"),
        {"u": form_data.username}
    )
    user = result.fetchone()
    
    # If using placeholders or initial setup
    if user and user._mapping["password_hash"] == "placeholder_hash":
        # First time login basically, update hash
        new_hash = get_password_hash(form_data.password)
        await db.execute(text("UPDATE users SET password_hash = :p WHERE username = :u"), {"p": new_hash, "u": form_data.username})
        await db.commit()
    elif not user or not verify_password(form_data.password, user._mapping["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user._mapping["username"], "is_admin": user._mapping["is_admin"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user["id"]),
        username=current_user["username"],
        is_admin=current_user["is_admin"],
        avatar_id=current_user["avatar_id"]
    )
