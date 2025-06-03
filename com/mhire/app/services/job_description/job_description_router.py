import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from com.mhire.app.services.job_description.job_description import JobDescription
from com.mhire.app.services.job_description.job_description_schema import (
    JobDescriptionRequest,
    JobDescriptionResponse,
    ErrorResponse
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/job",
    tags=["job-description"],
    responses={
        404: {"model": ErrorResponse, "description": "Not found"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)

@router.post("/description",
    response_model=JobDescriptionResponse,
    summary="Generate a job description",
    description="Generate a professional job description based on provided details"
)
async def generate_job_description(request: JobDescriptionRequest) -> JobDescriptionResponse:
    try:
        # Create JobDescription instance
        job_desc_generator = JobDescription()
        
        # Generate the description
        result = await job_desc_generator.generate_description(request.dict())
        
        # Return the response
        return JobDescriptionResponse(
            status=result["status"],
            message=result["message"],
            job_description=result["job_description"]
        )
            
    except HTTPException as he:
        # Re-raise HTTP exceptions as they are
        raise he
    except Exception as e:
        logger.error(f"Error handling request: {str(e)}")
        error = ErrorResponse(
            status_code=500,
            detail="Internal server error",
            error_type="UnexpectedError",
            timestamp=datetime.now().isoformat()
        )
        return JSONResponse(
            status_code=500,
            content=error.dict()
        )