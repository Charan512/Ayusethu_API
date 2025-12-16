# backend/routes/public.py (FINAL VERSION)

from fastapi import APIRouter, HTTPException
from app.database import batches_col
from app.ipfs_handler import get_public_url
from app.models.public import PublicBatchDetails, Stage, MediaItem
from app.blockchain_client import verify_token
from datetime import datetime
from typing import List

router = APIRouter()

def _format_date(dt: object) -> str:
    """Safely formats a datetime object or returns N/A."""
    return dt.strftime('%Y-%m-%d %H:%M') if isinstance(dt, datetime) else "N/A"

@router.get("/api/public/scan/{product_unit_id}", response_model=PublicBatchDetails, tags=["public"])
async def public_consumer_scan(product_unit_id: str):
    """
    Public, unauthenticated endpoint to fetch the full verified supply chain journey.
    It searches by the unique Product Unit ID (from the QR code), with a fallback to Batch ID.
    """
    
    # 1. Search for the batch document using the unique Product Unit ID
    batch_doc = await batches_col.find_one({
        "packaging_data.unit_id": product_unit_id
    })
    
    # 2. Fallback: If not found by unit ID, try searching by the raw batch_id
    if not batch_doc:
         batch_doc = await batches_col.find_one({"batch_id": product_unit_id})
    
    if not batch_doc:
        raise HTTPException(status_code=404, detail=f"Product or Batch ID {product_unit_id} not found.")

    packaging_info = batch_doc.get('packaging_data', {})
    
    # --- CRITICAL: Live Public Chain Verification ---
    verification_result = await verify_token(product_unit_id) 
    is_verified_public = verification_result.get("verified", False)
    public_chain_tx = verification_result.get("txHash") 
    
    # -------------------------------------------------------------
    
    stages_list: List[Stage] = []
    stage_counter = 1
    collector_info = batch_doc.get('collector_data', {})
    
    # 1. Growth Stages (Source: Collector's proof in growth_data)
    for i in range(1, 6):
        stage_key = f"stage_{i}"
        stage_data = batch_doc.get('growth_data', {}).get(stage_key)

        if stage_data and stage_data.get('cid'):
            photos = [MediaItem(
                id=1,
                title=f"Verification Photo",
                url=get_public_url(stage_data['cid']),
                description=stage_data.get('notes', 'Collector verification proof.')
            )]
            
            stages_list.append(Stage(
                id=stage_counter,
                name=f"Cultivation Stage {i} Verified",
                date=_format_date(stage_data.get('updated_at')),
                location=batch_doc.get('location', 'Farm Location'),
                description=f"Stage {i} proof submitted by Collector {collector_info.get('name', 'N/A')}.",
                photos=photos,
            ))
            stage_counter += 1

    # 2. Lab Testing Stage (Source: lab_data)
    lab_data = batch_doc.get('lab_data')
    if lab_data and lab_data.get('report_cid') and lab_data.get('submitted_at'):
        report_cid = lab_data['report_cid']
        
        photos = [MediaItem(
            id=1,
            title="Official Lab Test Report",
            url=get_public_url(report_cid),
            description=f"Purity Test Results: {'Passed' if lab_data.get('results', {}).get('passed') else 'Failed'}."
        )]
        
        stages_list.append(Stage(
            id=stage_counter,
            name="Quality Testing & Lab Verification",
            date=_format_date(lab_data.get('submitted_at')),
            location=f"Lab Tester: {lab_data.get('tester_name', 'N/A')}",
            description=f"Batch tested and confirmed {batch_doc.get('status').upper()} for purity.",
            photos=photos,
        ))
        stage_counter += 1

    # 3. Manufacturing & Packaging Stage
    mfg_data = batch_doc.get('manufacturer_data') 
    mfg_submission = batch_doc.get('manufacturing_data', {})
    
    if batch_doc.get('status') in ["manufacturing_done", "packaged"] and mfg_data: 
        mfg_date = batch_doc.get('packaged_at') or mfg_submission.get('submitted_at')
        
        stages_list.append(Stage(
            id=stage_counter,
            name="Manufacturing & Final Packaging",
            date=_format_date(mfg_date),
            location=mfg_data.get('name', 'GMP Facility'),
            description=f"Product packaged by {mfg_data.get('name')}. Final Product ID: {packaging_info.get('unit_id', product_unit_id)}.",
            photos=[], 
        ))
        stage_counter += 1

    # --- Final Construction and Status Determination ---
    display_id = packaging_info.get('unit_id') or product_unit_id
    
    final_status = batch_doc.get('status', 'PENDING')
    
    # Override status based on public chain verification for the consumer view
    if final_status == 'packaged' and is_verified_public:
        final_status = 'VERIFIED_ON_PUBLIC_CHAIN'
    elif final_status == 'packaged' and not is_verified_public:
        final_status = 'WARNING_PUBLIC_ANCHOR_MISSING' 

    return PublicBatchDetails(
        productName=batch_doc.get('herb_name', 'Herbal Product'),
        batchId=display_id,
        status=final_status,
        farmerName=batch_doc.get('farmer_name', 'N/A'),
        farmLocation=batch_doc.get('location', 'N/A'),
        # Prioritize the Public Chain TX Hash, fallback to Fabric TX Hash
        blockchainTxHash=public_chain_tx or packaging_info.get('fabric_final_tx'),
        processingStages=stages_list,
    )