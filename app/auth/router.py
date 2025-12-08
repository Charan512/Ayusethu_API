# backend/app/auth/router.py
import os, shutil, json
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from app.auth.models import LoginRequest, TokenResponse, UserPublic
from app.auth.crud import hash_password, create_user, verify_user_credentials, get_user_by_email
from app.auth.deps import get_db, create_access_token, get_current_user
from bson import ObjectId

router = APIRouter(prefix="/auth", tags=["auth"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/register", response_model=UserPublic)
async def register(
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    meta_json: str = Form(None),
    file: UploadFile = File(None),
    db=Depends(get_db),
):
    exists = await get_user_by_email(db, email)
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    meta = {}
    if meta_json:
        try:
            meta = json.loads(meta_json)
        except:
            meta = {}

    if file:
        fname = f"{ObjectId()}_{file.filename}"
        dest = os.path.join(UPLOAD_DIR, fname)
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        meta["uploaded_file"] = dest

    hashed = hash_password(password)
    doc = await create_user(db, email=email, full_name=full_name, hashed_password=hashed, role=role, meta=meta)
    return UserPublic(id=str(doc["_id"]), email=doc["email"], full_name=doc["full_name"], role=doc["role"], meta=doc.get("meta"))

@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db=Depends(get_db)):
    user = await verify_user_credentials(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    sub = str(user["_id"]) if "_id" in user else str(user["id"])
    token, expires_in = create_access_token(subject=sub, extra={"role": user.get("role")})
    return TokenResponse(access_token=token, expires_in=expires_in)

@router.get("/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    user["id"] = str(user["_id"])
    return UserPublic(id=user["id"], email=user["email"], full_name=user["full_name"], role=user["role"], meta=user.get("meta"))
