# app/routes/batches.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.blockchain_client import create_batch, get_batch, list_batches
import httpx

router = APIRouter(prefix="/api", tags=["batches"])

class BatchCreate(BaseModel):
    batchId: str
    farmerId: str
    collectorId: str
    herbName: str
    geo1: str
    geo2: str
    harvestDate: str
    grade: str
    speciesScore: int
    geoScore: int
    notes: str | None = None

@router.post("/batches")
async def create_batch_endpoint(batch: BatchCreate):
    try:
        result = await create_batch(batch.dict())
        return result
    except httpx.HTTPError as e:
        # Pass through error from bridge/Fabric
        detail = getattr(e.response, "json", lambda: {})()
        raise HTTPException(
            status_code=500,
            detail=detail.get("error") if isinstance(detail, dict) else str(e),
        )

@router.get("/batches/{batch_id}")
async def get_batch_endpoint(batch_id: str):
    try:
        result = await get_batch(batch_id)
        return result
    except httpx.HTTPError as e:
        detail = getattr(e.response, "json", lambda: {})()
        raise HTTPException(
            status_code=500,
            detail=detail.get("error") if isinstance(detail, dict) else str(e),
        )

@router.get("/batches")
async def list_batches_endpoint():
    try:
        result = await list_batches()
        return result
    except httpx.HTTPError as e:
        detail = getattr(e.response, "json", lambda: {})()
        raise HTTPException(
            status_code=500,
            detail=detail.get("error") if isinstance(detail, dict) else str(e),
        )
