import hashlib
import secrets
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from fastapi import Header, HTTPException, status, Depends
from db.manager import db_manager

logger = logging.getLogger("sidecar.logic.auth")

# Security Configuration
SECRET_KEY = os.environ.get("BETA_SECRET_KEY", "706a6563742d62657461-756c747261-736563726574")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

def get_password_hash(password: str) -> str:
    """Uses PBKDF2 with a random salt."""
    salt = secrets.token_bytes(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + hash_obj.hex()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a PBKDF2 hash against a plain password."""
    try:
        salt_hex, hash_hex = hashed_password.split(":")
        salt = bytes.fromhex(salt_hex)
        hash_to_verify = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, 100000)
        return hash_to_verify.hex() == hash_hex
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Dependency for FastAPI routes to validate JWT and return users.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Fetch user from DB
    conn = db_manager.connect()
    user = conn.execute("SELECT id, username, role, full_name FROM users WHERE username = ?", (username,)).fetchone()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    return {
        "id": user[0],
        "username": user[1],
        "role": user[2],
        "full_name": user[3]
    }

async def check_admin(user: dict = Depends(get_current_user)):
    """Dependency to restrict routes to ADMIN only."""
    if user["role"] != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation restricted to Administrators"
        )
    return user
