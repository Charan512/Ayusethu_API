# backend/app/models/public.py (NEW FILE)

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MediaItem(BaseModel):
    id: int
    title: str
    url: str = Field(description="The public IPFS gateway URL derived from the CID.")
    description: Optional[str] = None
    duration: Optional[str] = None 

class Stage(BaseModel):
    id: int
    name: str
    date: str = Field(description="Formatted date of the stage completion.")
    location: str
    description: str
    photos: List[MediaItem] = []
    audio: Optional[MediaItem] = None

class PublicBatchDetails(BaseModel):
    productName: str
    batchId: str
    status: str
    farmerName: str
    farmLocation: str
    blockchainTxHash: Optional[str] = None
    processingStages: List[Stage] = Field(description="Chronological list of all verifiable supply chain events.")