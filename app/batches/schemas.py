from uuid import UUID
from typing import Optional
from pydantic import BaseModel

from app.batches.models import BatchRowStatus


class BatchRowRead(BaseModel):
    row: int
    status: BatchRowStatus
    name: Optional[str]
    hospital_id: Optional[int]
    error_msg: Optional[str]


class BatchSummary(BaseModel):
    batch_id: UUID
    total_hospital: int
    processed_hospital: int
    failed_hospital: int
    processing_time_second: Optional[float]
    batch_activated: Optional[bool]
    hospitals: list[BatchRowRead]




