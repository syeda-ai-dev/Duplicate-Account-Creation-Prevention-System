import logging
import os
import uuid
from fastapi import HTTPException
from typing import Dict, List, Optional
import requests
from datetime import datetime

from com.mhire.app.config.config import Config
from com.mhire.app.database.db_manager import DBManager
from com.mhire.app.services.face_verification.face_verification_schema import FaceVerificationMatch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaceVerification:
    def __init__(self):
        self.config = Config()
        self.confidence_threshold = 88  # 88% confidence threshold
        
        # Set Face++ API credentials and endpoints from config
        self.api_key = self.config.fpp_api_key
        self.api_secret = self.config.fpp_api_secret
        self.detect_url = self.config.fpp_detect
        self.search_url = self.config.fpp_search
        self.create_url = self.config.fpp_create
        self.add_url = self.config.fpp_add
        
        # Initialize database manager
        self.db_manager = DBManager()

    async def get_faceset_detail(self, outer_id: str) -> Optional[Dict]:
        """Get details of a FaceSet from Face++ API"""
        try:
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'outer_id': outer_id
            }
            
            response = requests.post(self.config.fpp_get_detail, data=data)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error getting FaceSet details: {str(e)}")
            return None

    async def create_new_faceset(self) -> Optional[str]:
        """Create a new FaceSet"""
        try:
            # Generate new outer_id
            new_outer_id = f"fraud_protection_set_{uuid.uuid4().hex[:8]}"
            
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'display_name': f"Fraud Protection Set {uuid.uuid4().hex[:8]}",
                'outer_id': new_outer_id,
                'tags': 'fraud_protection'
            }
            
            response = requests.post(self.create_url, data=data)
            response.raise_for_status()
            
            # Add to local metadata
            await self.db_manager.add_new_faceset(new_outer_id)
            
            return new_outer_id
            
        except Exception as e:
            logger.error(f"Error creating new FaceSet: {str(e)}")
            return None

    async def add_face_to_faceset(self, face_token: str, outer_id: str) -> bool:
        """Add a face token to a specific FaceSet"""
        try:
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'face_tokens': face_token,
                'outer_id': outer_id
            }
            
            response = requests.post(self.add_url, data=data)
            response.raise_for_status()
            
            # Get updated face count
            details = await self.get_faceset_detail(outer_id)
            if details:
                await self.db_manager.update_faceset_count(outer_id, details.get('face_count', 0))
            
            # Save face token with its FaceSet ID
            await self.db_manager.save_face_token(face_token, outer_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding face to FaceSet: {str(e)}")
            return False

    async def find_or_create_faceset(self) -> Optional[str]:
        """Find an available FaceSet or create a new one"""
        try:
            # Try to find an existing FaceSet with capacity
            faceset_info = await self.db_manager.find_available_faceset()
            
            if faceset_info:
                outer_id, _ = faceset_info
                return outer_id
                
            # Create new FaceSet if none available
            return await self.create_new_faceset()
            
        except Exception as e:
            logger.error(f"Error finding or creating FaceSet: {str(e)}")
            return None

    async def detect_face(self, image_data: bytes) -> str:
        """Detect face and get face token from Face++ API"""
        try:
            files = {'image_file': image_data}
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret
            }
            
            response = requests.post(self.detect_url, files=files, data=data)
            response.raise_for_status()
            
            result = response.json()
            if not result.get('faces'):
                raise HTTPException(status_code=400, detail="No face detected in the image")
                
            return result['faces'][0]['face_token']
            
        except requests.RequestException as e:
            logger.error(f"Face++ API error during detection: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to detect face")

    async def search_similar_faces(self, face_token: str) -> List[FaceVerificationMatch]:
        """Search for similar faces across all FaceSets"""
        try:
            matches = []
            metadata = await self.db_manager.get_faceset_metadata()
            
            # Search in each FaceSet
            for outer_id in metadata.keys():
                data = {
                    'api_key': self.api_key,
                    'api_secret': self.api_secret,
                    'face_token': face_token,
                    'outer_id': outer_id,
                    'return_result_count': 5
                }
                
                try:
                    response = requests.post(self.search_url, data=data)
                    response.raise_for_status()
                    
                    result = response.json()
                    
                    for result_face in result.get('results', []):
                        confidence = result_face.get('confidence', 0)
                        if confidence >= self.confidence_threshold:
                            matches.append(FaceVerificationMatch(
                                confidence=confidence,
                                face_token=result_face.get('face_token')
                            ))
                except Exception as e:
                    logger.warning(f"Error searching FaceSet {outer_id}: {str(e)}")
                    continue
            
            return sorted(matches, key=lambda x: x.confidence, reverse=True)
            
        except Exception as e:
            logger.error(f"Error during face search: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to search for similar faces")

    async def save_face_data(self, face_token: str) -> bool:
        """Save face token and add to appropriate FaceSet"""
        try:
            # Find or create a FaceSet with available capacity
            outer_id = await self.find_or_create_faceset()
            if not outer_id:
                return False
            
            # Add face to FaceSet
            success = await self.add_face_to_faceset(face_token, outer_id)
            if not success:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving face data: {str(e)}")
            return False

    async def verify_face(self, image_data: bytes) -> Dict:
        """Main verification flow"""
        # Step 1: Detect face and get face token
        face_token = await self.detect_face(image_data)
        
        # Step 2: Search for similar faces across all FaceSets
        matches = await self.search_similar_faces(face_token)
        
        # Step 3: Process results
        status = "success"
        message = "New face registered successfully"
        is_duplicate = False
        confidence = None
        top_matches = []

        if not matches:
            # No matches above threshold - save as new face
            success = await self.save_face_data(face_token)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to save face data")
        else:
            # Found matches above threshold
            best_match = matches[0]
            is_duplicate = best_match.confidence >= self.confidence_threshold
            confidence = best_match.confidence
            top_matches = matches[:3]
            
            if is_duplicate:
                status = "duplicate"
                message = "Face match found - access denied"
            else:
                # Not a duplicate, save the new face
                success = await self.save_face_data(face_token)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to save face data")

        result = {
            "status": status,
            "message": message,
            "face_token": face_token,
            "is_duplicate": is_duplicate,
            "matches": top_matches
        }
        
        if confidence is not None:
            result["confidence"] = confidence
            
        return result