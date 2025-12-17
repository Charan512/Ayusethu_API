from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime

# ==============================
# MongoDB Connection
# ==============================

MONGO_URI = os.getenv("MONGO_URI")
client = AsyncIOMotorClient(MONGO_URI)
database = client["ayusethu_db"]

users_col = database["users"]
batches_col = database["batches"]
quotes_col = database["quotes"]
manufacturing_col = database["manufacturing"]
packaging_col = database["packaging"]
notification_collection = database["notifications"]


# ==============================
# Helpers
# ==============================

def object_id_to_str(doc: dict | None):
    if not doc:
        return None
    new_doc = dict(doc)
    new_doc["_id"] = str(new_doc["_id"])
    return new_doc




# ==============================
# USER SCHEMA (Login / Register)
# ==============================

"""
Frontend (Login.jsx) sends:

- role
- fullName
- email
- password
- phone (Collector)
- organization (Collector)
- labName, licenseNumber (Tester)
- companyName, licenseNumber (Manufacturer)
"""

def user_helper(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "fullName": user.get("fullName"),
        "email": user.get("email"),
        "role": user.get("role"),
        "phone": user.get("phone"),
        "organization": user.get("organization"),
        "labName": user.get("labName"),
        "companyName": user.get("companyName"),
        "licenseNumber": user.get("licenseNumber"),
        "createdAt": user.get("createdAt"),
    }


# ==============================
# BATCH SCHEMA (CORE DOCUMENT)
# ==============================

"""
This SINGLE document supports:
- Collector
- Lab
- Manufacturer
- Public Scan
"""

def batch_helper(batch: dict) -> dict:
    return {
        "id": batch.get("batch_id"),
        "name": batch.get("herb_name"),
        "status": batch.get("status"),
        "quantity": batch.get("quantity"),  # optional / may be None
        "testScore": batch.get("lab_data", {}).get("summary", {}).get("quality_score", 0),
        "testDetails": batch.get("lab_data", {}).get("summary", {}).get("test_breakdown", {}),
        "farmerName": batch.get("farmer_name"),
        "farmLocation": batch.get("location"),
        "createdAt": batch.get("createdAt").isoformat() if batch.get("createdAt") else None
    }



# ==============================
# FULL BATCH DOCUMENT STRUCTURE
# ==============================

"""
Batch document shape (single source of truth)
"""

def new_batch_document(batch_id: str) -> dict:
    return {
        "batch_id": batch_id,
        "status": "created",
        "createdAt": datetime.utcnow(),

        # =========================
        # FARMER DATA
        # =========================
        "farmer": {
            "id": None,
            "name": None,
            "location": None,
        },

        # =========================
        # COLLECTOR DATA
        # =========================
        "collector": {
            "id": None,
            "name": None,

            "stage1": {
                "visitDate": None,
                "species": None,
                "estimated_quantity": None,
                "irrigation_type": None,
                "soil_type": None,
                "gps": None,
                "address": None,
                "notes": None,
                "farm_photo_cid": None,
            },

            "stage5": {
                "finalHarvestDate": None,
                "final_quantity": None,
                "sample_collected": None,
                "gps": None,
                "final_photo_cid": None,
                "dispatch_authorized": False,
            },
        },

        # =========================
        # LAB DATA
        # =========================
        "lab": {
            "assigned_lab_id": None,
            "assigned_lab_name": None,
            "acceptedAt": None,

            "herb_info": {},
            "identity_tests": {},
            "physicochemical": {},
            "phytochemical": {},
            "contaminants": {},

            "final_decision": {
                "passed": None,
                "rejection_reason": None,
                "technician": None,
                "test_date": None,
                "report_cid": None,
                "comments": None,
            },

            "summary": {
                "quality_score": 0,
                "test_breakdown": {},
            },
        },

        # =========================
        # MANUFACTURER DATA
        # =========================
        "bids": [],

        "manufacturer": {
            "id": None,
            "name": None,

            "manufacturing": {
                "received": {
                    "quantity": None,
                    "timestamp": None,
                },
                "processing": {
                    "washing_date": None,
                    "drying": {
                        "date": None,
                        "temperature": None,
                    },
                    "grinding_date": None,
                    "extraction": {
                        "method": None,
                        "details": None,
                    },
                },
                "storage_conditions": None,
                "final_quantity": None,
                "product_form": None,
                "geo_tag": None,
                "certificate_cid": None,
                "photo_cids": [],
            },
        },

        # =========================
        # PACKAGING
        # =========================
        "packaging": {
            "label_id": None,
            "printed_at": None,
            "packaging_batch_number": None,
            "barcode": None,
        },

        # =========================
        # BLOCKCHAIN
        # =========================
        "blockchain": {
            "batch_tx": None,
            "lab_tx": None,
            "manufacturing_tx": None,
            "packaging_tx": None,
        },
    }


# ==============================
# NOTIFICATIONS (ALL ROLES)
# ==============================

def notification_helper(notification: dict) -> dict:
    created_at = notification.get("createdAt")
    return {
        "id": str(notification["_id"]),
        "user_id": notification.get("user_id"),
        "role": notification.get("role"),
        "category": notification.get("category"),
        "title": notification.get("title"),
        "message": notification.get("message"),
        "batch_id": notification.get("batch_id"),
        "read": notification.get("read", False),
        "createdAt": created_at.isoformat() if created_at else None,
    }

