# backend/app/auth/models.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any

class RegisterCommon(BaseModel):
    full_name: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = Field(...)

class RoleData(BaseModel):
    phone: Optional[str] = None
    organization: Optional[str] = None
    lab_name: Optional[str] = None
    lab_license: Optional[str] = None
    location: Optional[str] = None
    company_name: Optional[str] = None
    manufacturing_license: Optional[str] = None
    plot_id: Optional[str] = None

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str
    meta: Optional[Dict[str, Any]] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    meta: Optional[Dict[str, Any]] = None
