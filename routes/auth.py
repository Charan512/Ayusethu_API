from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime

from app.database import users_col, user_helper
from utils.jwt import create_token
import os

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

router = APIRouter(prefix="/auth", tags=["Auth"])

# ================ CHANGE THIS ================
# From bcrypt to pbkdf2_sha256 (no password length limit)
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
# ============================================

# =========================
# REQUEST MODELS
# =========================

class RegisterRequest(BaseModel):
    role: str
    fullName: str
    email: EmailStr
    password: str
    phone: str | None = None
    organization: str | None = None
    labName: str | None = None
    companyName: str | None = None
    licenseNumber: str | None = None
    
    # ================ REMOVE OR KEEP VALIDATOR ================
    # Optional: Keep for security but not required for length
    @validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v
    # ========================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: str
    
    # ================ REMOVE OR KEEP VALIDATOR ================
    # Optional: Keep for consistency
    @validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v
    # ========================================================

# =========================
# REGISTER
# =========================

@router.post("/register")
async def register_user(data: RegisterRequest):
    if data.role == "Admin":
        raise HTTPException(status_code=403, detail="Admin cannot be registered")

    if await users_col.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="Email already exists")

    # Build user document
    user_doc = {
        "fullName": data.fullName,
        "email": data.email,
        "role": data.role,
        "passwordHash": pwd_ctx.hash(data.password),  # This will work with pbkdf2
        "createdAt": datetime.utcnow(),
    }
    
    # Add role-specific fields
    if data.role == "Collector":
        if data.phone:
            user_doc["phone"] = data.phone
        if data.organization:
            user_doc["organization"] = data.organization
            
    elif data.role == "Tester":
        if data.labName:
            user_doc["labName"] = data.labName
        if data.licenseNumber:
            user_doc["licenseNumber"] = data.licenseNumber
            
    elif data.role == "Manufacturer":
        if data.companyName:
            user_doc["companyName"] = data.companyName
        if data.licenseNumber:
            user_doc["licenseNumber"] = data.licenseNumber

    await users_col.insert_one(user_doc)
    return {"message": "Registered successfully"}


# =========================
# LOGIN
# =========================

@router.post("/login")
async def login_user(data: LoginRequest):
    # -------- ADMIN LOGIN --------
    if data.role == "Admin":
        if data.email != ADMIN_EMAIL or data.password != ADMIN_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid admin credentials")

        token = create_token({
            "id": "ADMIN",
            "role": "Admin",
            "email": ADMIN_EMAIL,
            "name": "Admin"
        })

        return {
            "user": {
                "id": "ADMIN",
                "role": "Admin",
                "email": ADMIN_EMAIL,
                "name": "Admin"
            },
            "access_token": token
        }

    # -------- NORMAL USERS --------
    user = await users_col.find_one({
        "email": data.email,
        "role": data.role
    })

    if not user or "passwordHash" not in user or not pwd_ctx.verify(data.password, user["passwordHash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({
        "id": str(user["_id"]),
        "role": user["role"],
        "email": user["email"],
        "name": user.get("fullName", "User")
    })

    return {
        "user": user_helper(user),
        "access_token": token
    }