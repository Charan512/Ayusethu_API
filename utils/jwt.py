from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

# =========================
# CONFIG
# =========================

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 1440))

security = HTTPBearer()

# =========================
# TOKEN CREATE
# =========================

def create_token(data: dict):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# =========================
# TOKEN DECODE (LOW LEVEL)
# =========================

def decode_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

# =========================
# FASTAPI DEPENDENCY (THIS IS NEW)
# =========================

def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        payload = decode_token(token)
        return payload   # {id, role, email, exp}
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
