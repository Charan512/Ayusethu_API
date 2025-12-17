from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File, Request
from app.database import batches_col, batch_helper, notification_collection, notification_helper
from utils.jwt import verify_token
from utils.notify import notify
from pydantic import BaseModel # Import models used in main.py
from datetime import datetime
import random
from bson import ObjectId
# Assuming ActorAssign model is defined elsewhere or moved here. We'll define it here for safety.
class ActorAssign(BaseModel):
    id: str
    name: str
    visit_date: str | None = None # Added based on common use case

# 🛑 CRITICAL: Base path for all Admin routes in this file
router = APIRouter(prefix="/admin", tags=["Admin"]) 

# 1. Dashboard (The root data fetch) - Frontend call: adminApi.get("dashboard")
@router.get("/dashboard") 
async def admin_dashboard(user=Depends(verify_token)):
    if user["role"] != "Admin":
        raise HTTPException(403)
    return {"batches": [batch_helper(b) async for b in batches_col.find()]}

# 2. Assign Collector - Frontend call: adminApi.put("assign-collector/{batch_id}")
@router.put("/assign-collector/{batch_id}")
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

# 3. Select Manufacturer - Frontend call: adminApi.post("select-manufacturer")
@router.post("/select-manufacturer")
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

# 4. Get Quotes - Frontend call: adminApi.get("quotes/{batch_id}")
@router.get("/quotes/{batch_id}")
async def get_quotes(batch_id: str, user=Depends(verify_token)):
    if user["role"] != "Admin":
        raise HTTPException(403)

    batch = await batches_col.find_one({"batch_id": batch_id})
    if not batch:
        raise HTTPException(404)

    return batch.get("quotes", [])
    
# 5. Publish Tester Request - Frontend call: adminApi.post("publish-tester-request")
@router.post("/publish-tester-request")
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
    
# 6. /admin/collectors (Requires DB logic to fetch lists of users by role)
@router.get("/collectors")
async def admin_collectors(user=Depends(verify_token)):
    if user["role"] != "Admin":
        raise HTTPException(403)
    # Placeholder for actual DB fetch
    return [{"id": "C-101", "name": "Collector 1", "region": "North", "status": "active", "rating": 4.5, "assignedBatches": 10, "completed": 8, "avgTime": "2 days", "accuracy": "99%"}] 

# 7. /admin/testers
@router.get("/testers")
async def admin_testers(user=Depends(verify_token)):
    if user["role"] != "Admin":
        raise HTTPException(403)
    # Placeholder for actual DB fetch
    return [{"id": "T-201", "name": "Test Lab 1", "accreditation": "ISO", "turnaround": "36 hrs", "accuracy": "99.1%", "acceptanceRate": "95%", "rating": 4.8, "status": "active"}] 

# 8. /admin/manufacturers
@router.get("/manufacturers")
async def admin_manufacturers(user=Depends(verify_token)):
    if user["role"] != "Admin":
        raise HTTPException(403)
    # Placeholder for actual DB fetch
    return [{"id": "M-301", "name": "Mfg Co 1", "status": "active"}]