from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from database import batch_collection, batch_helper, database
from ipfs_handler import upload_to_ipfs
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import json
import random

app = FastAPI()

# Allow Frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Collections ---
user_collection = database.get_collection("users")

# --- Pydantic Models ---
class BatchCreate(BaseModel):
    species: str
    farmId: str
    startDate: str
    coords: str

class ActorAssign(BaseModel):
    id: str
    name: str

class BidSelection(BaseModel):
    batch_id: str
    manufacturer_id: str
    manufacturer_name: str
    winning_price: float

class UserLogin(BaseModel):
    email: str
    password: str
    role: str

class UserRegister(BaseModel):
    email: str
    password: str
    role: str
    fullName: str
    phone: Optional[str] = None
    labName: Optional[str] = None
    licenseNumber: Optional[str] = None
    location: Optional[str] = None
    companyName: Optional[str] = None
    organization: Optional[str] = None

# ==========================================
# 0. AUTHENTICATION (Standard)
# ==========================================
@app.post("/api/auth/register")
async def register_user(user: UserRegister):
    existing_user = await user_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_dict = user.dict()
    user_dict["created_at"] = datetime.now()
    result = await user_collection.insert_one(user_dict)
    return {"message": "User registered successfully", "userId": str(result.inserted_id)}

@app.post("/api/auth/login")
async def login_user(user: UserLogin):
    existing_user = await user_collection.find_one({"email": user.email, "role": user.role})
    if not existing_user or existing_user["password"] != user.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "message": "Login successful",
        "user": {
            "name": existing_user["fullName"],
            "email": existing_user["email"],
            "role": existing_user["role"],
            "id": str(existing_user["_id"])
        }
    }

# ==========================================
# 1. FARMER ENDPOINTS (Stages 2, 3, 4 Logic Added)
# ==========================================
@app.post("/api/farmer/register")
async def register_batch(data: BatchCreate):
    new_batch = {
        "batch_id": f"BATCH-{int(datetime.now().timestamp())}",
        "herb_name": data.species,
        "farmer_id": data.farmId,
        "farmer_name": "Ramesh Kumar", 
        "quantity": 0,
        "location": data.coords,
        "status": "planting",
        "timeline": {"planting": data.startDate},
        "created_at": datetime.now()
    }
    await batch_collection.insert_one(new_batch)
    return {"message": "Success"}

@app.get("/api/farmer/crops/{farmer_id}")
async def get_farmer_crops(farmer_id: str):
    batches = []
    async for batch in batch_collection.find({"farmer_id": farmer_id}):
        batches.append(batch_helper(batch))
    return batches

# NEW: Explicit Farmer Updates for Stages 2, 3, 4
@app.post("/api/farmer/update-growth")
async def update_growth(
    batch_id: str = Form(...),
    stage: int = Form(...),
    notes: str = Form(...),
    photo: UploadFile = File(...)
):
    content = await photo.read()
    cid = await upload_to_ipfs(content, photo.filename)
    
    await batch_collection.update_one(
        {"batch_id": batch_id},
        {"$set": {
            f"timeline.stage_{stage}": datetime.now().isoformat(),
            f"growth_data.stage_{stage}": {"cid": cid, "notes": notes},
            "status": f"growing_stage_{stage}"
        }}
    )
    return {"message": f"Stage {stage} Updated by Farmer"}

# ==========================================
# 2. ADMIN ENDPOINTS (Selection Logic Added)
# ==========================================
@app.get("/api/admin/dashboard")
async def get_admin_data():
    batches = []
    async for batch in batch_collection.find():
        batches.append(batch_helper(batch))
    return {"batches": batches}

@app.put("/api/admin/assign-collector/{batch_id}")
async def assign_collector(batch_id: str, actor: ActorAssign):
    await batch_collection.update_one(
        {"batch_id": batch_id},
        {"$set": {
            "collector_data": {"id": actor.id, "name": actor.name},
            "status": "collection_assigned",
            "timeline.collection_assigned": datetime.now().isoformat()
        }}
    )
    return {"message": "Assigned"}

@app.post("/api/admin/broadcast-to-labs/{batch_id}")
async def broadcast_to_labs(batch_id: str):
    await batch_collection.update_one(
        {"batch_id": batch_id},
        {"$set": {"status": "waiting_for_lab"}}
    )
    return {"message": "Broadcasted to Labs"}

# NEW: Admin selects winning manufacturer (Step 3b)
@app.post("/api/admin/select-manufacturer")
async def select_manufacturer(bid: BidSelection):
    # Generate Label ID as per workflow Step 3e
    label_id = f"LBL-{bid.batch_id}-{random.randint(1000,9999)}"
    
    await batch_collection.update_one(
        {"batch_id": bid.batch_id},
        {"$set": {
            "manufacturer_data": {
                "id": bid.manufacturer_id, 
                "name": bid.manufacturer_name,
                "agreed_price": bid.winning_price,
                "label_id": label_id # Stored here, sent to manuf later
            },
            "status": "manufacturing_assigned",
            "timeline.manufacturer_assigned": datetime.now().isoformat()
        }}
    )
    return {"message": "Manufacturer Selected & Label ID Generated"}

# ==========================================
# 3. COLLECTOR ENDPOINTS (Stages 1 & 5)
# ==========================================
@app.post("/api/ml/identify")
async def identify_herb(photo: UploadFile = File(...)):
    herbs = ["Tulsi (Holy Basil)", "Ashwagandha", "Turmeric", "Neem"]
    detected = random.choice(herbs)
    return {"success": True, "species": detected, "confidence": 0.98}

@app.post("/api/collector/update-stage")
async def update_stage(
    batch_id: str = Form(...),
    stage: str = Form(...), # 1 or 5
    photo: UploadFile = File(...)
):
    content = await photo.read()
    cid = await upload_to_ipfs(content, photo.filename)
    
    status_update = "growing" if stage == "1" else "collected"
    
    await batch_collection.update_one(
        {"batch_id": batch_id},
        {"$set": {
            f"collector_data.stage_{stage}_cid": cid,
            "status": status_update,
            f"timeline.collector_stage_{stage}": datetime.now().isoformat()
        }}
    )
    return {"message": "Stage Updated", "cid": cid}

# ==========================================
# 4. LAB ENDPOINTS (First Accept Logic)
# ==========================================
# NEW: First Accept Logic (Step 2b)
@app.post("/api/lab/accept-task")
async def accept_task(
    batch_id: str = Body(..., embed=True),
    lab_id: str = Body(..., embed=True),
    lab_name: str = Body(..., embed=True)
):
    # Check if already assigned (Locking mechanism)
    batch = await batch_collection.find_one({"batch_id": batch_id})
    if batch.get("lab_data", {}).get("id"):
        raise HTTPException(status_code=400, detail="Batch already assigned to another lab")

    await batch_collection.update_one(
        {"batch_id": batch_id},
        {"$set": {
            "lab_data": {"id": lab_id, "name": lab_name},
            "status": "testing_assigned",
            "timeline.lab_assigned": datetime.now().isoformat()
        }}
    )
    return {"message": "Task Accepted"}

@app.post("/api/lab/submit")
async def submit_lab_result(
    batch_id: str = Form(...),
    result_json: str = Form(...),
    report: UploadFile = File(None)
):
    data = json.loads(result_json)
    cid = None
    if report:
        content = await report.read()
        cid = await upload_to_ipfs(content, report.filename)

    # If pass -> Open for Bidding (Step 3a)
    status = "bidding_open" if data.get("passed") else "rejected"
    
    await batch_collection.update_one(
        {"batch_id": batch_id},
        {"$set": {
            "lab_data.results": data,
            "lab_data.report_cid": cid,
            "status": status,
            "lab_data.quality_score": 95 if data.get("passed") else 40
        }}
    )
    return {"message": "Lab Result Saved"}

# ==========================================
# 5. MANUFACTURER ENDPOINTS
# ==========================================
@app.get("/api/manufacturer/batches")
async def get_manuf_batches():
    batches = []
    # Manufacturer sees batches open for bidding OR assigned to them
    async for batch in batch_collection.find({"status": {"$in": ["bidding_open", "manufacturing_assigned", "manufacturing"]}}):
        b_data = batch_helper(batch)
        b_data["name"] = b_data["herb_name"]
        b_data["testScore"] = batch.get("lab_data", {}).get("quality_score", 0)
        batches.append(b_data)
    return batches

@app.post("/api/manufacturer/quote")
async def submit_quote(
    batch_id: str = Body(..., embed=True),
    manufacturer_id: str = Body(..., embed=True),
    amount: float = Body(..., embed=True)
):
    # Add bid to a list of bids in the document
    await batch_collection.update_one(
        {"batch_id": batch_id},
        {"$push": {"bids": {"manufacturer_id": manufacturer_id, "amount": amount, "timestamp": datetime.now().isoformat()}}}
    )
    return {"message": "Quote Submitted"}

@app.post("/api/manufacturer/submit-process")
async def submit_process(
    batch_id: str = Form(...),
    process_data: str = Form(...),
):
    await batch_collection.update_one(
        {"batch_id": batch_id},
        {"$set": {
            "manufacturer_data.process": json.loads(process_data),
            "status": "packaging"
        }}
    )
    return {"message": "Process Recorded"}

# ==========================================
# 6. USER ENDPOINT
# ==========================================
@app.get("/api/public/scan/{batch_id}")
async def public_scan(batch_id: str):
    batch = await batch_collection.find_one({"batch_id": batch_id})
    if batch:
        data = batch_helper(batch)
        return {
            "code": data["batch_id"],
            "name": data["herb_name"],
            "farmerName": data["farmer_name"],
            "region": data["location"],
            "qualityGrade": "A+" if data["complianceScore"] > 90 else "B",
            "purity": f"{data['complianceScore']}%",
            "harvestDate": data["timeline"].get("collection_assigned", "Pending"),
            "status": data["status"],
            "description": "Verified Authentic via VirtuHerbChain Blockchain."
        }
    raise HTTPException(status_code=404, detail="Batch not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)