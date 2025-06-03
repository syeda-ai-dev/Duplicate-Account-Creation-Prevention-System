from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class JobDescriptionRequest(BaseModel):
    job_title: str
    job_location: str
    salary_range: Optional[str] = None
    work_hours: Optional[str] = None
    job_type: str
    job_requirements: str

class JobDescriptionResponse(BaseModel):
    status: str
    message: str
    job_description: Optional[str] = None

class ErrorResponse(BaseModel):
    status_code: int
    detail: str
    error_type: Optional[str] = None
    timestamp: Optional[str] = datetime.now().isoformat()
