import logging
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from com.mhire.app.services.verification_system.face_verification.face_verification import FaceVerification
from com.mhire.app.services.verification_system.face_verification.face_verification_schema import VerificationResponse, ErrorResponse

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

ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/jpg']

@router.post("/verify", 
    response_model=VerificationResponse,
    summary="Verify a face image",
    description="""Upload a face image to verify against existing faces and prevent duplicates.
    Image requirements:
    - File size: Maximum 2MB
    - Format: JPEG, PNG
    - Dimensions: Between 48x48 and 4096x4096 pixels
    - Must contain a clear, unobstructed face"""
)
async def verify_face(file: UploadFile = File(...)) -> VerificationResponse:
    try:
        # Validate MIME type
        if file.content_type not in ALLOWED_MIME_TYPES:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": f"Invalid file type. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}",
                    "is_duplicate": False,
                    "face_token": None,
                    "confidence": None,
                    "matches": None
                }
            )
            
        # Read image data with size limit
        try:
            image_data = await file.read()
            if not image_data:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Empty image file",
                        "is_duplicate": False,
                        "face_token": None,
                        "confidence": None,
                        "matches": None
                    }
                )
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": f"Error reading image file: {str(e)}",
                    "is_duplicate": False,
                    "face_token": None,
                    "confidence": None,
                    "matches": None
                }
            )
            
        # Create FaceVerification instance and process image
        face_verifier = FaceVerification()
        result = await face_verifier.verify_face(image_data)
            
        # Return error response if status is error
        if result.get("status") == "error":
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": result.get("message", "Error processing image"),
                    "is_duplicate": False,
                    "face_token": None,
                    "confidence": None,
                    "matches": None
                }
            )
            
        # Return verification response for successful case
        return VerificationResponse(
            status=result["status"],
            message=result["message"],
            confidence=result.get("confidence"),
            face_token=result["face_token"],
            is_duplicate=result["is_duplicate"],
            matches=result.get("matches")
        )
            
    except Exception as e:
        logger.error(f"Error handling request: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Internal server error: {str(e)}",
                "is_duplicate": False,
                "face_token": None,
                "confidence": None,
                "matches": None
            }
        )