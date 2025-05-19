import logging

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

@router.post("/verify", 
    response_model=VerificationResponse,
    summary="Verify a face image",
    description="Upload a face image to verify against existing faces and prevent duplicates"
)
async def verify_face(file: UploadFile = File(...)) -> VerificationResponse:
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "File must be an image",
                    "is_duplicate": False,
                    "face_token": None,
                    "confidence": None,
                    "matches": None
                }
            )
            
        # Read image data
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
            
        # Create FaceVerification instance
        face_verifier = FaceVerification()
        
        try:
            # Process the image for face verification
            result = await face_verifier.verify_face(image_data)
            
            # Return error response if status is error
            if result.get("status") == "error":
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": result.get("message", "No face detected in image"),
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
            # Log the error and return a structured error response
            logger.error(f"Error during face verification: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Error processing image. Please try again with a clear face image.",
                    "is_duplicate": False,
                    "face_token": None,
                    "confidence": None,
                    "matches": None
                }
            )
            
    except Exception as e:
        logger.error(f"Error handling request: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Internal server error",
                "is_duplicate": False,
                "face_token": None,
                "confidence": None,
                "matches": None
            }
        )