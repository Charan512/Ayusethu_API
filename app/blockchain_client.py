# backend/app/blockchain_client.py (FINAL, FIXED VERSION)
import os
import httpx
from datetime import datetime
import uuid

# --- Separate Configuration Constants ---
FABRIC_BRIDGE_URL = os.getenv("FABRIC_BRIDGE_URL", "http://localhost:3000") 
POLYGON_VERIFICATION_URL = os.getenv("POLYGON_VERIFICATION_URL", "http://4.213.152.206:3000") 
# ----------------------------------------


async def create_batch(payload: dict) -> dict:
    """Anchors data to the private chain (Hyperledger Fabric mock)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{FABRIC_BRIDGE_URL}/batches", json=payload)
        resp.raise_for_status()
        return resp.json() 
    except Exception as e:
        print(f"Fabric bridge anchor failed: {e}")
        return {"error": "Fabric anchor failed", "txHash": f"0xFABRIC_FAIL_{uuid.uuid4().hex[:12]}"}

async def get_batch(batch_id: str) -> dict:
    """Retrieves batch data from the Fabric bridge."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # FIX: Use FABRIC_BRIDGE_URL
            resp = await client.get(f"{FABRIC_BRIDGE_URL}/batches/{batch_id}")
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise httpx.HTTPError(f"Failed to fetch batch from Fabric bridge: {e}")


async def list_batches() -> dict:
    """Retrieves list of all batches from the Fabric bridge."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # FIX: Use FABRIC_BRIDGE_URL
            resp = await client.get(f"{FABRIC_BRIDGE_URL}/batches")
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise httpx.HTTPError(f"Failed to list batches from Fabric bridge: {e}")


async def verify_token(token_id: str) -> dict:
    """Calls the live public chain API to verify NFT existence."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{POLYGON_VERIFICATION_URL}/verify/token/{token_id}")
        resp.raise_for_status()
        return resp.json() 
    except httpx.HTTPStatusError as e:
        print(f"Public chain token verification failed (HTTP status {e.response.status_code}): {e.response.text}")
        return {"verified": False, "error": f"Verification failed: {e.response.text}"}
    except Exception as e:
        print(f"Public chain network error: {e}")
        return {"verified": False, "error": "Public chain service unreachable"}