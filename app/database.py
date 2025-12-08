import motor.motor_asyncio
from bson import ObjectId

# Update if your Mongo URI is different
MONGO_DETAILS = "mongodb://localhost:27017"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
database = client.ayusethu_db
batch_collection = database.get_collection("batches")

# Helper to format MongoDB documents for Frontend
def batch_helper(batch) -> dict:
    return {
        "id": str(batch["_id"]),
        "batch_id": batch.get("batch_id"),
        "herb_name": batch.get("herb_name"),
        "farmer_id": batch.get("farmer_id"),
        "farmer_name": batch.get("farmer_name"),
        "quantity": batch.get("quantity"),
        "status": batch.get("status"),
        "location": batch.get("location"),
        "timeline": batch.get("timeline", {}),
        "collector": batch.get("collector_data", {}).get("name"),
        "collector_id": batch.get("collector_data", {}).get("id"),
        "tester": batch.get("lab_data", {}).get("name"),
        "manufacturer": batch.get("manufacturer_data", {}).get("name"),
        "test_results": batch.get("lab_data", {}).get("results", {}),
        "complianceScore": batch.get("lab_data", {}).get("quality_score", 0),
        "ipfs_data": batch.get("ipfs_data", []),
        # Add fields expected by specific UI components
        "herb": batch.get("herb_name"), 
        "farmer": batch.get("farmer_name"),
    }