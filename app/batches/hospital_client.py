import requests

from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class Hospital(BaseModel):
    name: str
    address: str
    phone: Optional[str]
    creation_batch_id: UUID


class HospitalClient:
    BASE_URL = "https://hospital-directory.onrender.com/hospitals/"

    @classmethod
    def activate_batch(cls, batch_id: UUID):
        res = requests.patch(
            f"{cls.BASE_URL}batch/{batch_id}/activate",
        )
        return res.status_code == 200, res

    @classmethod
    def upload_hospital(cls, hospital_data: Hospital):
        res = requests.post(
            cls.BASE_URL,
            data=hospital_data.model_dump_json()
        )
        return res.status_code == 200, res
