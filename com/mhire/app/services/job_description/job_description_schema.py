from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class JobDescriptionRequest(BaseModel):
    title: str
    companyName: str
    companyDetails: Optional[str] = None
    location: str
    salaryRange: Optional[str] = None
    workHours: Optional[str] = None
    type: List[str]
    skills: List[str]
    position: Optional[str]
    qualification: Optional[str] = None
    experience: Optional[str] = None
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
