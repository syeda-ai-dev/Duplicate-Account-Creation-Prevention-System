import logging
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional

from com.mhire.app.services.face_verification.face_verification import FaceVerification
from com.mhire.app.services.face_verification.face_verification_schema import VerificationResponse, ErrorResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/face",
    tags=["face-verification"],
    responses={
        404: {"model": ErrorResponse, "description": "Not found"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)

@router.post("/verify", 
    response_model=VerificationResponse,
    summary="Verify a face image",
    description="Upload a face image to verify against existing faces and prevent duplicates"
)
async def verify_face(file: UploadFile = File(...)) -> VerificationResponse:
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
            
        # Read image data
        image_data = await file.read()
        if not image_data:
            raise HTTPException(status_code=400, detail="Empty image file")
            
        # Create FaceVerification instance
        face_verifier = FaceVerification()
        
        # Process the image for face verification
        result = await face_verifier.verify_face(image_data)
        
        # Return verification response
        return VerificationResponse(
            status=result["status"],
            message=result["message"],
            confidence=result.get("confidence"),
            face_token=result["face_token"],
            is_duplicate=result["is_duplicate"],
            matches=result.get("matches")
        )
        
    except HTTPException as he:
        # Re-raise HTTP exceptions as they are already properly formatted
        raise he
    except Exception as e:
        logger.error(f"Error during face verification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

