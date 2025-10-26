from uuid import UUID
from typing import List
from datetime import timedelta, datetime, UTC
from sqlmodel import Session, select, func
from fastapi import HTTPException

from app.batches.models import Batch, BatchRow, BatchStatus, BatchRowStatus
from app.batches.schemas import BatchSummary, BatchRowRead
from app.batches.hospital_client import Hospital, HospitalClient


# --------- Summarise Batch ---------
def get_batch_summaries(session: Session, batch_ids: List[UUID]) -> List[BatchSummary]:
    """
    Fetch batch summaries for one or more batch IDs.
    """
    rows = session.exec(
        select(BatchRow)
        .where(BatchRow.batch_id.in_(batch_ids))
        .options()
    ).all()

    batches: dict[str, Batch] = {}
    batch_map: dict[str, list[BatchRow]] = {}
    for batch in session.exec(select(Batch).where(Batch.id.in_(batch_ids))).all():
        batches[str(batch.id)] = batch
        batch_map[str(batch.id)] = []

    for row in rows:
        batch_map[str(row.batch_id)].append(row)

    summaries: list[BatchSummary] = []
    for batch_id, batch_rows in batch_map.items():
        batch = batches.get(batch_id)
        total = len(batch_rows)
        success = sum(r.status in BatchRowStatus.CREATED_AND_ACTIVATED for r in batch_rows)
        failed = sum(r.status == BatchRowStatus.FAILED for r in batch_rows)

        processing_time_second = None
        if batch and batch.processing_start_at and batch.processing_finished_at:
            processing_duration: timedelta = batch.processing_finished_at - batch.processing_start_at
            processing_time_second = processing_duration.total_seconds()

        summaries.append(
            BatchSummary(
                batch_id=batch_id,
                total_hospital=total,
                processed_hospital=success,
                failed_hospital=failed,
                processing_time_second=processing_time_second,
                batch_activated=batch.batch_activated,
                hospitals=[
                    BatchRowRead(
                        row=r.row,
                        status=r.status,
                        name=r.name,
                        hospital_id=r.hospital_id,
                        error_msg=r.error_msg
                    )
                    for r in batch_rows
                ],
            )
        )
    return summaries

def get_batch_summary(session: Session, batch_id: UUID) -> BatchSummary | None:
    summaries = get_batch_summaries(session, [batch_id])
    return summaries[0] if summaries else None

# --------- Process batch -----------
async def process_batch(session: Session, batch_id: UUID):
    batch = session.get(Batch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    if batch.status != BatchStatus.CREATED:
        # This means the batch is already being processed or
        # is already processed.
        return
    
    # Set the batch status to 'PROCESSING' and record the start time
    batch.status = BatchStatus.PROCESSING
    batch.processing_start_at = datetime.now(UTC)
    session.add(batch)
    session.commit()

    try:
        data = await batch.read_csv_file()

        fail_count = 0
        for idx, row in enumerate(data):
            # Create a new BatchRow entry for each row in the CSV
            batch_row = BatchRow(
                batch_id=batch_id,
                row=idx + 1,
                status=BatchRowStatus.CREATING
            )
            session.add(batch_row)
            session.commit()

            try:
                is_uploaded, upload_response = HospitalClient.upload_hospital(
                    Hospital(creation_batch_id=batch_id, **row)
                )

                if is_uploaded:
                    batch_row.status = BatchRowStatus.CREATED
                    
                    response_data = upload_response.json()
                    batch_row.name = response_data.get("name")
                    batch_row.hospital_id = response_data.get("id")
                else:
                    batch_row.status = BatchRowStatus.FAILED
                    batch_row.error_msg = f"Upload failed: {upload_response.text}"
                    print(f"\t{batch_row.error_msg}")
                    fail_count += 1
            
            except Exception as exc:
                batch_row.status = BatchRowStatus.FAILED
                batch_row.error_msg = f"Exception occurred: {str(exc)}"
                fail_count += 1
            
            # Save the BatchRow after processing each row
            session.add(batch_row)
            session.commit()

        if fail_count == 0:
            batch.status = BatchStatus.UPLOADED
            session.add(batch)
            session.commit()

            is_activated, activate_response = HospitalClient.activate_batch(batch_id)

            if is_activated:
                batch.batch_activated = True
                batch.status = BatchStatus.SUCCESSFUL
                batch.message = "Batch successfully uploaded and activated"
            else:
                batch.status = BatchStatus.FAILED
                batch.message = f"Activation failed: {activate_response.text}"
        else:
            batch.batch_activated = False
            batch.status = BatchStatus.UPLOADING_FAILED
    except Exception as exc:
        batch.status = BatchStatus.FAILED
        batch.message = f"Error occured while processing batch: {exc}"
    finally:
        batch.processing_finished_at = datetime.now(UTC)
        session.add(batch)
        session.commit()
