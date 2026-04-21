from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import List
from datetime import datetime
from db.manager import db_manager
from logic.auth import get_password_hash, verify_password, create_access_token, get_current_user, check_admin
from models.api_models import Token, UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
async def register_user(user_in: UserCreate):
    """
    Registers a new user.
    Logic: If no users exist, the first user is automatically an ADMIN.
    """
    conn = db_manager.connect()
    
    # Check if user already exists
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (user_in.username,)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Username already registered")

    # Check if this is the first user
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    role = "ADMIN" if user_count == 0 else user_in.role

    hashed_pw = get_password_hash(user_in.password)
    
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (username, hashed_password, role, full_name) VALUES (?, ?, ?, ?)",
                (user_in.username, hashed_pw, role, user_in.full_name)
            )
            user_id = cursor.lastrowid
            
        return {
            "id": user_id,
            "username": user_in.username,
            "role": role,
            "full_name": user_in.full_name,
            "created_at": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Standard OAuth2 compatible token login.
    """
    conn = db_manager.connect()
    user = conn.execute("SELECT username, hashed_password, role FROM users WHERE username = ?", (form_data.username,)).fetchone()
    
    if not user or not verify_password(form_data.password, user[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user[0]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user[0],
        "role": user[2]
    }

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user
