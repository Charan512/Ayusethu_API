import json, random, os, httpx, uuid
from fastapi import FastAPI, Depends, UploadFile, File, Form, Request, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pydantic import BaseModel
from ml.inference import predict_species
from utils.jwt import verify_token
from utils.notify import notify
from app.database import notification_collection, notification_helper, batches_col, batch_helper
from app.ipfs_handler import upload_to_ipfs
# ROUTERS
from routes.auth import router as auth_router
from routes.batches import router as batch_router
from routes.public import router as public_router
from .blockchain_client import create_batch 
from bson import ObjectId

app = FastAPI()

# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= ROUTERS =================
app.include_router(auth_router)
app.include_router(batch_router)
app.include_router(public_router) 
# ================= CONFIG =================

# ================= MODELS =================
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

# =====================================================
# 1️⃣ COLLECTOR / FARMER FLOW
# =====================================================

@app.post("/api/collector/create-batch")
async def create_batch_endpoint(data: BatchCreate, user=Depends(verify_token)): # Renamed function to avoid conflict
    if user["role"] != "Collector":
        raise HTTPException(403, "Collectors only")

    batch_id = f"BATCH-{uuid.uuid4().hex[:10].upper()}"

    batch = {
        "batch_id": batch_id,
        "herb_name": data.species,
        "farmer_id": data.farmId,
        "farmer_name": "Unknown",
        "location": data.coords,
        "status": "planting",
        "timeline": {"planting": data.startDate},
        "createdAt": datetime.utcnow(),
        "collector_data": {
            "id": user["id"],
            "name": user.get("name", "Collector")
        }
    }

    await batches_col.insert_one(batch)

    # --- Initial Fabric Anchor: Basic Facts Only ---
    await create_batch({
        "batchId": batch_id,
        "farmerId": data.farmId,
        "collectorId": user["id"],
        "herbName": data.species.upper(),
        "geo1": data.coords,
        "harvestDate": data.startDate,
        "grade": "INITIAL",      # Placeholder
        "speciesScore": 0,       # Placeholder
        "geoScore": 0,           # Placeholder
    })
    # --- END Initial Anchor ---
    
    await notify(
    user_id=data.farmId,
    role="Farmer",
    title="New Batch Created",
    message=f"A new batch {batch_id} has been registered for your farm",
    batch_id=batch_id,
    category="batch"
    )
    return {"batchId": batch_id}
@app.get("/api/farmer/crops/{farmer_id}")
async def farmer_crops(farmer_id: str, user=Depends(verify_token)):
    if user["role"] != "Farmer" or user["id"] != farmer_id:
        raise HTTPException(403)

    return [batch_helper(b) async for b in batches_col.find({"farmer_id": farmer_id})]

@app.post("/api/farmer/update-stage")
async def farmer_update_stage(
    batch_id: str = Body(...),
    stage: int = Body(...),
    data: dict = Body(...),
    user=Depends(verify_token)
):
    if user["role"] != "Farmer":
        raise HTTPException(403)

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch or batch["farmer_id"] != user["id"]:
        raise HTTPException(403)

    await batches_col.update_one(
        {"batch_id": batch_id},
        {"$set": {f"farmer_updates.stage_{stage}": data, "status": f"farmer_stage_{stage}_submitted"}}
    )
    return {"message": "Stage submitted"}

# ✅ FIX: Renamed to /api/collector/update-stage, removed farmer alias
@app.post("/api/collector/update-stage")
async def collector_update_stage(
    batch_id: str = Form(...),
    stage: int = Form(...),
    notes: str = Form(...),
    photo: UploadFile = File(...),
    user=Depends(verify_token)
):
    if user["role"] != "Collector":
        raise HTTPException(403)

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch or batch["collector_data"]["id"] != user["id"]:
        raise HTTPException(403)

    cid = await upload_to_ipfs(await photo.read(), photo.filename)

    await batches_col.update_one(
        {"batch_id": batch_id},
        {"$set": {
            f"growth_data.stage_{stage}": {
                "cid": cid,
                "notes": notes,
                "updated_at": datetime.utcnow()
            },
            f"timeline.stage_{stage}": datetime.utcnow().isoformat(),
            "status": f"growing_stage_{stage}"
        }}
    )
    return {"message": f"Stage {stage} updated"}

@app.post("/api/collector/verify-leaf")
async def verify_leaf(
    batch_id: str = Form(...),
    image: UploadFile = File(...),
    user=Depends(verify_token)
):
    if user["role"] != "Collector":
        raise HTTPException(403, "Collectors only")

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404, "Batch not found")

    image_bytes = await image.read()

    predicted_species = predict_species(image_bytes)
    expected_species = batch["herb_name"]

    match = predicted_species.lower() == expected_species.lower()
    if match:
        await batches_col.update_one(
        {"batch_id": batch_id},
        {"$set": {"ml_verified": True}}
    )

    if not match:
        await notify(
            user_id=batch["farmer_id"],
            role="Farmer",
            title="Species Mismatch Detected",
            message=f"ML verification failed for batch {batch_id}",
            batch_id=batch_id,
            category="ml"
        )

    return {
        "batch_id": batch_id,
        "predicted_species": predicted_species,
        "expected_species": expected_species,
        "match": match
    }

# \u2705 FIX: Added missing collector batch endpoints
@app.get("/api/collector/batches")
async def collector_batches(user=Depends(verify_token)):
    if user["role"] != "Collector":
        raise HTTPException(403)
    
    return [batch_helper(b) async for b in batches_col.find({
        "collector_data.id": user["id"]
    })]

@app.get("/api/collector/batch/{batch_id}")
async def collector_batch(batch_id: str, user=Depends(verify_token)):
    if user["role"] != "Collector":
        raise HTTPException(403)
    
    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch or batch.get("collector_data", {}).get("id") != user["id"]:
        raise HTTPException(403, "Not your batch")
    
    return batch_helper(batch)

# ✅ CRITICAL: User profile validation
@app.get("/api/auth/me")
async def get_current_user(user=Depends(verify_token)):
    """Get current authenticated user info"""
    return {
        "id": user["id"],
        "name": user.get("name", "User"),
        "role": user["role"],
        "email": user.get("email", "")
    }

# ✅ CRITICAL: Active batch restoration
@app.get("/api/collector/active-batch")
async def get_active_batch(user=Depends(verify_token)):
    """Get collector's active batch with full state"""
    if user["role"] != "Collector":
        raise HTTPException(403)
    
    # Find most recent batch assigned to this collector
    batch = await batches_col.find_one(
        {"collector_data.id": user["id"]},
        sort=[("createdAt", -1)]
    )
    
    if not batch:
        return None
    
    # Calculate current stage and completed stages
    stage_data = batch.get("growth_data", {})
    completed_stages = []
    current_stage = 1
    
    # Check which stages are completed
    for i in range(1, 6):
        if stage_data.get(f"stage_{i}"):
            completed_stages.append(i)
            current_stage = i + 1 if i < 5 else 5
    
    return {
        "batch_id": batch["batch_id"],
        "current_stage": min(current_stage, 5),
        "completed_stages": completed_stages,
        "stage_data": stage_data,
        "herb_name": batch.get("herb_name"),
        "farmer_id": batch.get("farmer_id"),
        "location": batch.get("location"),
        "ml_verified": batch.get("ml_verified", False)
    }

# ✅ CRITICAL: Fetch farmer submissions per stage
@app.get("/api/collector/batch/{batch_id}/stage/{stage}")
async def get_stage_data(batch_id: str, stage: int, user=Depends(verify_token)):
    """Get farmer's submission data for specific stage"""
    if user["role"] != "Collector":
        raise HTTPException(403)
    
    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404, "Batch not found")
    
    if batch.get("collector_data", {}).get("id") != user["id"]:
        raise HTTPException(403, "Not your batch")
    
    stage_key = f"stage_{stage}"
    stage_data = batch.get("growth_data", {}).get(stage_key, {})
    
    return {
        "photos": [stage_data.get("cid")] if stage_data.get("cid") else [],
        "notes": stage_data.get("notes", ""),
        "timestamp": stage_data.get("updated_at"),
        "status": "submitted" if stage_data else "pending",
        "submitted": bool(stage_data)  # \u2705 CRITICAL: Boolean flag for frontend
    }



# =====================================================
# 2️⃣ ADMIN FLOW
# =====================================================

@app.get("/api/admin/dashboard")
async def admin_dashboard(user=Depends(verify_token)):
    if user["role"] != "Admin":
        raise HTTPException(403)
    return {"batches": [batch_helper(b) async for b in batches_col.find()]}

@app.put("/api/admin/assign-collector/{batch_id}")
async def assign_collector(batch_id: str, actor: ActorAssign, user=Depends(verify_token)):
    if user["role"] != "Admin":
        raise HTTPException(403)

    await batches_col.update_one(
        {"batch_id": batch_id},
        {"$set": {
            "collector_data": actor.dict(),
            "status": "collection_assigned",
            "timeline.collection_assigned": datetime.utcnow().isoformat()
        }}
    )
    await notify(
    user_id=actor.id,
    role="Collector",
    title="New Collection Assigned",
    message=f"You have been assigned to batch {batch_id}",
    batch_id=batch_id,
    category="assignment"
    )

    return {"message": "Collector assigned"}

@app.post("/api/admin/select-manufacturer")
async def select_manufacturer(
    batch_id: str = Body(...),
    manufacturer_id: str = Body(...),
    user=Depends(verify_token)
):
    if user["role"] != "Admin":
        raise HTTPException(403)

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404)

    if batch["status"] != "bidding_open":
        raise HTTPException(400, "Batch not in bidding state")

    quote = next(
        (q for q in batch.get("quotes", []) if q["manufacturer_id"] == manufacturer_id),
        None
    )
    if not quote:
        raise HTTPException(400, "Selected manufacturer has no quote")

    label_id = f"LBL-{batch_id}-{random.randint(1000,9999)}"

    await batches_col.update_one(
        {"batch_id": batch_id},
        {"$set": {
            "manufacturer_data": {
                "id": manufacturer_id,
                "name": quote.get("manufacturer_name"),
                "price": quote["price"],
                "label_id": label_id
            },
            "status": "manufacturing_assigned"
        }}
    )
    await notify(
        user_id=manufacturer_id,
        role="Manufacturer",
        title="Manufacturing Assigned",
        message=f"You have been selected to manufacture batch {batch_id}",
        batch_id=batch_id,
        category="manufacturing"
    )

    return {"message": "Manufacturer selected"}

# =====================================================
# 3️⃣ LAB FLOW
# =====================================================
@app.post("/api/lab/accept")
async def accept_lab_task(batch_id: str = Body(...), user=Depends(verify_token)):
    if user["role"] != "Tester":
        raise HTTPException(403)

    # Atomic lock: only one tester can win
    result = await batches_col.update_one(
        {
            "batch_id": batch_id,
            "status": "testing_assigned"
        },
        {
            "$set": {
                "lab_data.tester_id": user["id"],
                "lab_data.name": user.get("name"),
                "lab_data.accepted_at": datetime.utcnow(),
                "status": "testing_in_progress"
            }
        }
    )

    if result.modified_count == 0:
        raise HTTPException(409, "Batch already accepted")
    await notification_collection.update_many(
    {"batch_id": batch_id, "role": "Tester"},
    {"$set": {"read": True}}
)
    return {"message": "Batch accepted"}

@app.get("/api/lab/batches")
async def lab_batches(user=Depends(verify_token)):
    if user["role"] != "Tester":
        raise HTTPException(403)

    return [batch_helper(b) async for b in batches_col.find({
        "$or": [{"status": "testing_assigned"}, {"lab_data.tester_id": user["id"]}]
    })]

@app.post("/api/lab/submit")
async def submit_lab(
    batch_id: str = Form(...),
    result_json: str = Form(...),
    report: UploadFile = File(None),
    user=Depends(verify_token)
):
    if user["role"] != "Tester":
        raise HTTPException(403)

    result = json.loads(result_json)
    cid = await upload_to_ipfs(await report.read(), report.filename) if report else None

    await batches_col.update_one(
    {"batch_id": batch_id},
    {"$set": {
        "lab_data.results": result,
        "lab_data.report_cid": cid,

        # ✅ ADD THESE 3 LINES
        "lab_data.tester_id": user["id"],
        "lab_data.tester_name": user.get("name"),
        "lab_data.submitted_at": datetime.utcnow(),

        "status": "bidding_open" if result.get("passed") else "rejected"
    }}
)


    if result.get("passed"):
        await notify(
        user_id="ALL_MANUFACTURERS",
        role="Manufacturer",
        title="Bidding Open",
        message=f"Bidding is now open for batch {batch_id}",
        batch_id=batch_id,
        category="bidding"
    )


    # Notify Farmer
    batch = await batches_col.find_one({"batch_id": batch_id})
    await notify(
        user_id=batch["farmer_id"],
        role="Farmer",
        title="Lab Results Ready",
        message=f"Lab results are available for batch {batch_id}",
        batch_id=batch_id,
        category="lab"
    )

    return {"message": "Lab submitted"}
@app.get("/api/lab/history")
async def lab_history(user=Depends(verify_token)):
    if user["role"] != "Tester":
        raise HTTPException(403)

    history = []
    async for b in batches_col.find({
        "lab_data.tester_id": user["id"]
    }).sort("lab_data.submitted_at", -1):
        history.append({
            "batch_id": b["batch_id"],
            "herb_name": b.get("herb_name"),
            "status": b.get("status"),
            "passed": b.get("lab_data", {}).get("results", {}).get("passed"),
            "submitted_at": b.get("lab_data", {}).get("submitted_at"),
            "report_cid": b.get("lab_data", {}).get("report_cid"),
        })

    return history

# =====================================================
# 4️⃣ PUBLIC SCAN
# =====================================================


# =====================================================
# 🔔 NOTIFICATIONS (ALL ROLES)
# =====================================================

@app.get("/api/notifications")
async def get_notifications(user=Depends(verify_token)):
    notifications = []
    async for n in notification_collection.find(
        {"user_id": user["id"]},
        sort=[("createdAt", -1)]
    ):
        notifications.append(notification_helper(n))
    return notifications

@app.put("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user=Depends(verify_token)):
    await notification_collection.update_one(
        {
            "_id": ObjectId(notification_id),
            "user_id": user["id"]
        },
        {"$set": {"read": True}}
    )
    return {"message": "Notification marked as read"}


# =====================================================
# 🛠️ UTILITIES
# =====================================================

@app.post("/api/utils/reverse-geocode")
async def reverse_geocode(lat: float = Body(...), lon: float = Body(...)):
    """Server-side reverse geocoding to avoid client rate limits"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json"},
                headers={"User-Agent": "VirtuHerbChain/1.0"}
            )
            return res.json()
    except Exception as e:
        raise HTTPException(500, f"Geocoding failed: {str(e)}")


# =====================================================
# ⛓️ BLOCKCHAIN ANCHORING
# =====================================================

@app.post("/api/blockchain/anchor-batch")
async def anchor_batch(batch_id: str = Body(...), user=Depends(verify_token)):
    """Anchor final batch status to blockchain after all verifications complete."""
    if user["role"] != "Collector":
        raise HTTPException(403, "Collectors only")
    
    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404, "Batch not found")
    
    if batch.get("collector_data", {}).get("id") != user["id"]:
        raise HTTPException(403, "Not your batch")
    
    # Check prerequisites: Must be lab-approved AND ML-verified
    is_lab_passed = batch.get("lab_data", {}).get("results", {}).get("passed", False)
    is_ml_verified = batch.get("ml_verified", False)
    
    if not is_lab_passed or not is_ml_verified:
        raise HTTPException(400, "Batch requires both ML verification and Lab approval before final anchoring.")
    
    if batch.get("blockchain_tx"):
        raise HTTPException(400, "Batch already anchored")
    
    # --- Final Fabric Anchor: Use Available Verification Data ---
    final_grade = "PASSED" if is_lab_passed else "FAILED"
    
    try:
        anchor_response = await create_batch({
            "batchId": batch_id,
            "farmerId": batch["farmer_id"],
            "collectorId": user["id"],
            "herbName": batch["herb_name"].upper(),
            "geo1": batch["location"],
            "grade": final_grade,
            "speciesScore": 100 if is_ml_verified else 0, 
            "geoScore": 100, 
        })
        
        tx_hash = anchor_response.get("txHash")
        if not tx_hash:
            raise Exception("Fabric bridge did not return a transaction hash.")
        
        await batches_col.update_one(
            {"batch_id": batch_id},
            {"$set": {
                "blockchain_tx": tx_hash,
                "status": "blockchain_anchored",
                "anchored_at": datetime.utcnow()
            }}
        )
        
        return {"tx_hash": tx_hash, "message": "Batch anchored to blockchain"}
    except Exception as e:
        raise HTTPException(500, f"Blockchain anchoring failed: {str(e)}")
@app.post("/api/manufacturer/submit-quote")
async def submit_quote(
    batch_id: str = Body(...),
    price: float = Body(...),
    validity: str = Body(...),
    notes: str = Body(""),
    user=Depends(verify_token)
):
    if user["role"] != "Manufacturer":
        raise HTTPException(403, "Manufacturers only")


    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404, "Batch not found")

    if batch["status"] != "bidding_open":
        raise HTTPException(400, "Bidding closed for this batch")

    # prevent duplicate bids
    existing = next(
        (q for q in batch.get("quotes", []) if q["manufacturer_id"] == user["id"]),
        None
    )
    if existing:
        raise HTTPException(400, "Quote already submitted")

    quote = {
    "quote_id": str(uuid.uuid4()),
    "manufacturer_id": user["id"],
    "manufacturer_name": user.get("name"),
    "price": price,
    "validity": validity,
    "notes": notes,
    "submitted_at": datetime.utcnow()
}


    await batches_col.update_one(
        {"batch_id": batch_id},
        {"$push": {"quotes": quote}}
    )

    return {"message": "Quote submitted successfully"}
@app.get("/api/admin/quotes/{batch_id}")
async def get_quotes(batch_id: str, user=Depends(verify_token)):
    if user["role"] != "Admin":
        raise HTTPException(403)

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404)

    return batch.get("quotes", [])
@app.post("/api/manufacturer/submit-manufacturing")
async def submit_manufacturing(
    request: Request,
    batch_id: str = Form(...),
    user=Depends(verify_token),
):

    if user["role"] != "Manufacturer":
        raise HTTPException(403)

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404)

    if batch["status"] != "manufacturing_assigned":
        raise HTTPException(400, "Manufacturing not allowed")

    if batch["manufacturer_data"]["id"] != user["id"]:
        raise HTTPException(403, "Not authorized")
    form = await request.form()
    await batches_col.update_one(
    {"batch_id": batch_id},
    {"$set": {
        "manufacturing_data": {
            "submitted_by": user["id"],
            "submitted_at": datetime.utcnow(),
            "raw_form": dict(form)  # store everything safely
        },
        "status": "manufacturing_done"
    }}
)
    return {"message": "Manufacturing data submitted"}
@app.post("/api/admin/publish-tester-request")
async def publish_tester_request(
    batch_id: str = Body(...),
    user=Depends(verify_token)
):
    if user["role"] != "Admin":
        raise HTTPException(403, "Admins only")

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404, "Batch not found")

    # Prevent duplicate publishing
    if batch.get("status") in ["testing_assigned", "testing_in_progress"]:
        raise HTTPException(400, "Testing already published or in progress")

    # Only allow after verification stage
    if batch.get("status") in [
    "testing_assigned",
    "testing_in_progress",
    "bidding_open",
    "manufacturing_assigned"
    ]:
        raise HTTPException(400, "Batch not eligible for lab testing")

    # Update batch state
    await batches_col.update_one(
        {"batch_id": batch_id},
        {
            "$set": {
                "status": "testing_assigned",
                "testing_published_at": datetime.utcnow()
            }
        }
    )

    # 🔔 Notify ALL testers (fan-out notification)
    await notify(
        user_id="ALL_TESTERS",
        role="Tester",
        title="New Lab Test Available",
        message=f"Batch {batch_id} is available for testing. First to accept will be assigned.",
        batch_id=batch_id,
        category="lab"
    )

    return {
        "message": "Tester request published successfully",
        "batch_id": batch_id
    }



@app.post("/api/manufacturer/complete-packaging")
async def complete_packaging(
    batch_id: str = Form(...),
    user=Depends(verify_token),
):
    if user["role"] != "Manufacturer":
        raise HTTPException(403)

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404)

    if batch["status"] != "manufacturing_done":
        raise HTTPException(400, "Packaging not allowed")

    if batch["manufacturer_data"]["id"] != user["id"]:
        raise HTTPException(403)
    product_unit_id = f"PROD-{uuid.uuid4().hex[:12].upper()}" 
    fabric_anchor_payload = {
        "unitId": product_unit_id,
        "batchId": batch_id,
        "manufacturerId": user["id"],
        "timestamp": datetime.utcnow().isoformat(),
    }
    anchor_response = await create_batch(fabric_anchor_payload)
    final_tx_hash = anchor_response.get("txHash") 
    await batches_col.update_one(
        {"batch_id": batch_id},
        {"$set": {
            "packaged_at": datetime.utcnow(),
            "status": "packaged",
            "packaging_data": { 
                "unit_id": product_unit_id,
                "fabric_final_tx": final_tx_hash,
            }
        }}
    )
    return {"message": "Packaging completed and anchored", "product_unit_id": product_unit_id}
async def manufacturer_batches(user=Depends(verify_token)):
    if user["role"] != "Manufacturer":
        raise HTTPException(403)

    return [
        batch_helper(b)
        async for b in batches_col.find({
            "$or": [
                {"status": "testing_assigned"},
                {
                    "status": "testing_in_progress",
                    "lab_data.tester_id": user["id"]
                }
            ]
        })
    ]
@app.get("/api/farmer/batches")
async def farmer_batches_simple(user=Depends(verify_token)):
    if user["role"] != "Farmer":
        raise HTTPException(403)
    return [batch_helper(b) async for b in batches_col.find({"farmer_id": user["id"]})]
@app.post("/api/farmer/submit-stage-proof")
async def farmer_submit_stage_proof(
    batch_id: str = Form(...),
    stage: int = Form(...),
    notes: str = Form(...),
    photo: UploadFile = File(...),
    user=Depends(verify_token)
):
    if user["role"] != "Farmer":
        raise HTTPException(403)

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch or batch["farmer_id"] != user["id"]:
        raise HTTPException(403, "Not your batch")
        
    cid = await upload_to_ipfs(await photo.read(), photo.filename)

    await batches_col.update_one(
        {"batch_id": batch_id},
        {"$set": {
            f"farmer_updates.stage_{stage}": {
                "cid": cid,
                "notes": notes,
                "updated_at": datetime.utcnow(),
                "submitted_by": user["id"]
            },
            "status": f"farmer_stage_{stage}_submitted" 
        }}
    )
    
    collector_id = batch.get("collector_data", {}).get("id")
    if collector_id:
        await notify(
            user_id=collector_id,
            role="Collector",
            title=f"Stage {stage} Ready",
            message=f"Farmer {user['full_name']} submitted proof for Batch {batch_id}. Review required.",
            batch_id=batch_id,
            category="review"
        )
    
    return {"message": f"Stage {stage} proof submitted to IPFS and pending Collector review."}