from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class JobDescriptionRequest(BaseModel):
    job_title: str
    company_name: str
    company_details: Optional[str] = None
    job_location: str
    salary_range: Optional[str] = None
    work_hours: Optional[str] = None
    job_type: str
    job_requirements: str
    vacancy: Optional[int] = 1
    qualification: Optional[str] = None
    years_of_experience: Optional[str] = None
    specialization: Optional[str] = None

class JobDescriptionSection(BaseModel):
    title: str
    content: str

class JobDescriptionResponse(BaseModel):
    status: str
    message: str
    sections: Optional[List[JobDescriptionSection]] = None

class ErrorResponse(BaseModel):
    status_code: int
    detail: str
    error_type: Optional[str] = None
    timestamp: Optional[str] = datetime.now().isoformat()
