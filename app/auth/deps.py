# backend/app/auth/deps.py
import os
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
from typing import Dict
from bson import ObjectId

# IMPORT THE FIXED DB INSTANCE
from app.database import db as global_db_instance

JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_ALG = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_EXPIRE_MIN = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

async def get_db():
    """
    Fetches the database connection from our global instance
    instead of trying to create a new (broken) one.
    """
    database = global_db_instance.get_db()
    if database is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    yield database

def create_access_token(subject: str, extra: Dict = None, expires_delta: int = None):
    to_encode = {"sub": str(subject)}
    if extra:
        to_encode.update(extra)
    expire = datetime.utcnow() + timedelta(minutes=(expires_delta or ACCESS_EXPIRE_MIN))
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALG)
    return token, int((expire - datetime.utcnow()).total_seconds())

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db=Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
        user = await db.users.find_one({"_id": ObjectId(sub)})
        
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
        user.pop("password", None)
        user["id"] = str(user["_id"])
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid")