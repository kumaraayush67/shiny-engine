import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel import Session, select
from typing import List

from app.database import get_db
from app.batches.models import Batch
from app.batches.schemas import BatchSummary
from app.batches.services import get_batch_summary, process_batch


router = APIRouter(prefix="", tags=["Batch"])


@router.get("/batch/", response_model=List[Batch])
async def list_batches(db: Session = Depends(get_db)):
    return db.exec(select(Batch)).all()


@router.get("/batch/{batch_id}", response_model=BatchSummary)
async def read_batch_summary(batch_id: uuid.UUID, db: Session = Depends(get_db)):
    summary = get_batch_summary(db, batch_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Batch not found")
    return summary


@router.post("/hospitals/bulk", response_model=BatchSummary)
async def create_batch(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Create
    batch = Batch()
    db.add(batch)
    db.commit()
    db.refresh(batch)

    # Upload and update
    try:
        await batch.upload_file(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.add(batch)
    db.commit()
    db.refresh(batch)

    # Process the batch
    await process_batch(db, batch.id)

    return get_batch_summary(db, batch.id)
