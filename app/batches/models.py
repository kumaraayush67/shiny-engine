import csv
import uuid
import aiofiles
from pathlib import Path
from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Dict, List
from io import StringIO

from sqlmodel import SQLModel, Field, JSON, Column, Relationship


RECORDS_DIR = Path("media/records")
RECORDS_DIR.mkdir(exist_ok=True)


class BatchStatus(str, Enum):
    CREATED = "created"
    PROCESSING = "processing"
    UPLOADED = "uploading"
    SUCCESSFUL = "successful"
    UPLOADING_FAILED = "uploading_failed"
    FAILED = "failed"


class Batch(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    # File info
    input_file: str = Field(nullable=True, description="Path or URL of the uploaded file")

    # Process info
    status: BatchStatus = Field(default=BatchStatus.CREATED, nullable=False)
    processing_start_at: Optional[datetime] = None
    processing_finished_at: Optional[datetime] = None
    message: Optional[str] = None
    process_breakdown: Dict = Field(default_factory=dict, sa_column=Column(JSON))

    batch_uploaded: bool = Field(default=False)
    batch_activated: bool = Field(default=False)

    # Retry info
    retry_count: int = Field(default=0)
    last_retry_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)

    rows: Optional[list["BatchRow"]] = Relationship(back_populates="batch")


    @property
    def file_path(self) -> Optional[Path]:
        return Path(self.input_file) if self.input_file else None

    @file_path.setter
    def file_path(self, path: Path):
        self.input_file = str(path)

    async def upload_file(self, file_obj):
        """
        Save uploaded file to disk and update the input_file field.
        """
        if not file_obj.filename.endswith(".csv"):
            raise ValueError("Only CSV files are allowed.")

        save_path = RECORDS_DIR / f"{self.id}.csv"
        with open(save_path, "wb") as f:
            content = await file_obj.read()
            f.write(content)

        self.file_path = save_path
        self.batch_uploaded = True
        return save_path

    async def read_csv_file(self) -> List[Dict]:
        """
        Asynchronously read the CSV input_file and return the content as a 
        list of dictionaries.
        """
        if not self.input_file:
            raise ValueError("No input file path provided")

        try:
            async with aiofiles.open(self.input_file, mode='r') as file:
                # Read the file content into a string
                file_content = await file.read()
                
                # Use StringIO to treat the string content as a file-like object
                csvfile = StringIO(file_content)
                reader = csv.DictReader(csvfile)

                return [row for row in reader]
        
        except FileNotFoundError:
            raise FileNotFoundError(f"The file at {self.input_file} was not found.")


class BatchRowStatus(str, Enum):
    PENDING = "pending"
    CREATING = "creating"
    CREATED = "created"
    CREATED_AND_ACTIVATED = "created_and_activated"
    FAILED = "failed"


class BatchRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    batch_id: uuid.UUID = Field(foreign_key="batch.id")
    row: int
    status: BatchRowStatus = Field(default=BatchRowStatus.PENDING)
    error_msg: Optional[str] = Field(nullable=True, description="Populate the reason in case of failure to be used for debugging")

    batch: Optional[Batch] = Relationship(back_populates="rows")

    # Use case specific data fields
    # we can make a JSON field to store this info
    # to make this Batch processing logic a bit more generalised.
    name: Optional[str] = None
    hospital_id: Optional[int] = None



