# backend/app/auth/crud.py
import time
from typing import Optional
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[dict]:
    return await db.users.find_one({"email": email})

async def create_user(db: AsyncIOMotorDatabase, email: str, full_name: str, hashed_password: str, role: str, meta: dict):
    doc = {
        "email": email,
        "full_name": full_name,
        "password": hashed_password,
        "role": role,
        "meta": meta or {},
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    doc.pop("password", None)
    doc["id"] = str(doc["_id"])
    return doc

async def verify_user_credentials(db: AsyncIOMotorDatabase, email: str, password: str) -> Optional[dict]:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.get("password", "")):
        return None
    user.pop("password", None)
    user["id"] = str(user["_id"])
    return user
