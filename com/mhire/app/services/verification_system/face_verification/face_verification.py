import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import io
from PIL import Image

from fastapi import HTTPException

from com.mhire.app.database.db_manager import DBManager
from com.mhire.app.services.verification_system.face_verification.face_verification_schema import FaceVerificationMatch, ErrorResponse, VerificationResponse
from com.mhire.app.services.verification_system.api_manager.faceplusplus_manager import FacePlusPlusManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaceVerification:
    def __init__(self):
        self.confidence_threshold = 90.0  # 88% confidence threshold
        self.fpp_manager = FacePlusPlusManager()
        self.db_manager = DBManager()
        # Face++ image requirements
        self.min_dimension = 48
        self.max_dimension = 4096
        self.max_file_size = 2 * 1024 * 1024  # 2MB in bytes

    def _validate_and_process_image(self, image_data: bytes) -> Tuple[bytes, bool, str]:
        """
        Validate and process the image according to Face++ requirements.
        Returns: (processed_image_data, is_valid, error_message)
        """
        try:
            # Check file size
            if len(image_data) > self.max_file_size:
                return None, False, "Image size exceeds 2MB limit. Please upload a smaller image."

            # Open and validate image
            img = Image.open(io.BytesIO(image_data))
            width, height = img.size

            # Check dimensions
            if width < self.min_dimension or height < self.min_dimension:
                return None, False, f"Image dimensions too small. Minimum size is {self.min_dimension}x{self.min_dimension} pixels."
            
            if width > self.max_dimension or height > self.max_dimension:
                # Resize image while maintaining aspect ratio
                aspect_ratio = width / height
                if width > height:
                    new_width = min(width, self.max_dimension)
                    new_height = int(new_width / aspect_ratio)
                else:
                    new_height = min(height, self.max_dimension)
                    new_width = int(new_height * aspect_ratio)
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Convert back to bytes
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format=img.format if img.format else 'JPEG', quality=85)
                image_data = img_byte_arr.getvalue()

                # Recheck file size after resizing
                if len(image_data) > self.max_file_size:
                    # Further compress if still too large
                    quality = 70
                    while len(image_data) > self.max_file_size and quality > 20:
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format=img.format if img.format else 'JPEG', quality=quality)
                        image_data = img_byte_arr.getvalue()
                        quality -= 10

                    if len(image_data) > self.max_file_size:
                        return None, False, "Unable to process image. Please upload a smaller image or reduce image quality."

            return image_data, True, ""

        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return None, False, "Invalid image format or corrupted image file."

    async def search_similar_faces(self, face_token: str) -> List[FaceVerificationMatch]:
        """Search for similar faces across all FaceSets"""
        try:
            matches = []
            facesets = await self.db_manager.get_all_stored_faces()
            
            for faceset_id, stored_tokens in facesets.items():
                if not stored_tokens:  # Skip empty facesets
                    continue
                    
                try:
                    results = await self.fpp_manager.search_faces(face_token, faceset_id)
                    
                    # Process matches above threshold
                    for result in results:
                        confidence = float(result.get('confidence', 0))
                        if confidence >= self.confidence_threshold:
                            matches.append(FaceVerificationMatch(
                                confidence=confidence,
                                face_token=result.get('face_token', '')
                            ))
                except Exception as e:
                    logger.warning(f"Error searching FaceSet {faceset_id}: {str(e)}")
                    continue
            
            return sorted(matches, key=lambda x: x.confidence, reverse=True)
            
        except Exception as e:
            logger.error(f"Error during face search: {str(e)}")
            error = ErrorResponse(status_code=500, detail=f"Error during face search: {str(e)}")
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def save_face_data(self, face_token: str) -> bool:
        """Save face token and add to appropriate FaceSet"""
        try:
            faceset_info = await self.db_manager.find_available_faceset()
            faceset_id = None
            
            if faceset_info:
                faceset_id = faceset_info[0]
                details = await self.fpp_manager.get_faceset_detail(faceset_id)
                if not details or 'error_message' in details:
                    logger.warning(f"Faceset {faceset_id} exists in database but not in Face++ API. Creating new faceset.")
                    faceset_id = None
            
            if not faceset_id:
                faceset_id = await self.fpp_manager.create_new_faceset()
                if not faceset_id:
                    error = ErrorResponse(status_code=500, detail="Failed to create new FaceSet in Face++ API")
                    raise HTTPException(status_code=error.status_code, detail=error.dict())

            added = await self.fpp_manager.add_face_to_faceset(face_token, faceset_id)
            if not added:
                error = ErrorResponse(status_code=500, detail=f"Failed to add face to FaceSet {faceset_id} in Face++ API")
                raise HTTPException(status_code=error.status_code, detail=error.dict())

            saved = await self.db_manager.save_face_token(face_token, faceset_id)
            if not saved:
                error = ErrorResponse(status_code=500, detail="Failed to save face token to database")
                raise HTTPException(status_code=error.status_code, detail=error.dict())

            details = await self.fpp_manager.get_faceset_detail(faceset_id)
            if details and 'face_count' in details:
                await self.db_manager.update_faceset_count(faceset_id, details['face_count'])
            
            logger.info(f"Successfully saved face token and added to FaceSet {faceset_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving face data: {str(e)}")
            error = ErrorResponse(status_code=500, detail=f"Error saving face data: {str(e)}")
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def verify_face(self, image_data: bytes) -> Dict:
        """Main verification flow - detect face, search for duplicates, save if new"""
        try:
            # Validate and process image
            processed_image, is_valid, error_message = self._validate_and_process_image(image_data)
            if not is_valid:
                return {
                    "status": "error",
                    "message": error_message,
                    "is_duplicate": False,
                    "face_token": None,
                    "confidence": None,
                    "matches": None
                }

            # Detect face using processed image
            face_token = await self.fpp_manager.detect_face(processed_image)
            if not face_token:
                return {
                    "status": "error",
                    "message": "No face detected in image. Please provide a clear image with a human face.",
                    "is_duplicate": False,
                    "face_token": None,
                    "confidence": None,
                    "matches": None
                }

            logger.info(f"Face detected with token: {face_token}")
            matches = await self.search_similar_faces(face_token)
            
            if matches:
                best_match = matches[0]
                return {
                    "status": "duplicate_found",
                    "message": "Potential duplicate face detected",
                    "is_duplicate": True,
                    "face_token": face_token,
                    "confidence": best_match.confidence,
                    "matches": matches
                }
            
            if not await self.save_face_data(face_token):
                return {
                    "status": "error",
                    "message": "Failed to save face data",
                    "is_duplicate": False,
                    "face_token": face_token,
                    "confidence": None,
                    "matches": None
                }

            return {
                "status": "success",
                "message": "New face found and token saved successfully",
                "face_token": face_token,
                "is_duplicate": False,
                "confidence": None,
                "matches": None
            }
            
        except Exception as e:
            logger.error(f"Error during face verification: {str(e)}")
            return {
                "status": "error",
                "message": f"Error processing image: {str(e)}. Please try again.",
                "is_duplicate": False,
                "face_token": None,
                "confidence": None,
                "matches": None
            }