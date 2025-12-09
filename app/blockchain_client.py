# app/blockchain_client.py
import os
import httpx

BLOCKCHAIN_BASE_URL = os.getenv("BLOCKCHAIN_BASE_URL", "http://localhost:3000")

async def create_batch(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(f"{BLOCKCHAIN_BASE_URL}/batches", json=payload)
    resp.raise_for_status()
    return resp.json()

async def get_batch(batch_id: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{BLOCKCHAIN_BASE_URL}/batches/{batch_id}")
    resp.raise_for_status()
    return resp.json()

async def list_batches() -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{BLOCKCHAIN_BASE_URL}/batches")
    resp.raise_for_status()
    return resp.json()
