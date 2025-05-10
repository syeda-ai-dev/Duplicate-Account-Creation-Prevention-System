import logging
import os
from fastapi import HTTPException
from typing import Dict, List
import requests
from datetime import datetime

from com.mhire.app.config.config import Config
from com.mhire.app.database.db_manager import DBManager
from .face_verification_schema import FaceVerificationMatch

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
        
        # Face Set configuration
        self.face_set_name = "fraud_protection_faces"
        self.face_set_tag = "fraud_protection"
        self.outer_id = "fraud_protection_set"
        
        # Initialize Face Set
        self._initialize_face_set()

    def _initialize_face_set(self):
        """Initialize or get existing Face Set"""
        try:
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'display_name': self.face_set_name,
                'outer_id': self.outer_id,
                'tags': self.face_set_tag
            }
            
            response = requests.post(self.create_url, data=data)
            
            if response.status_code == 400 and "FACESET_EXIST" in response.text:
                logger.info("Face Set already exists")
                return
                
            response.raise_for_status()
            logger.info("Face Set created successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Face Set: {str(e)}")

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
        """Search for similar faces using Face++ search API"""
        try:
            face_tokens = await self.db_manager.get_face_tokens()
            if not face_tokens:
                return []
            
            # Prepare face tokens string
            face_token_str = ','.join(face_tokens)
            
            # Search for similar faces in Face Set
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'face_token': face_token,
                'outer_id': self.outer_id,
                'return_result_count': 5  # Get top 5 matches
            }
            
            response = requests.post(self.search_url, data=data)
            response.raise_for_status()
            
            result = response.json()
            matches = []
            
            # Process search results
            for result_face in result.get('results', []):
                confidence = result_face.get('confidence', 0)
                if confidence >= self.confidence_threshold:
                    matches.append(FaceVerificationMatch(
                        confidence=confidence,
                        face_token=result_face.get('face_token')
                    ))
            
            return sorted(matches, key=lambda x: x.confidence, reverse=True)
            
        except requests.RequestException as e:
            logger.error(f"Face++ API error during search: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}")
            raise HTTPException(status_code=500, detail="Failed to search for similar faces")

    async def add_face_to_face_set(self, face_token: str) -> bool:
        """Add a face token to the Face Set"""
        try:
            data = {
                'api_key': self.api_key,
                'api_secret': self.api_secret,
                'face_tokens': face_token,
                'outer_id': self.outer_id
            }
            
            response = requests.post(self.add_url, data=data)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding face to Face Set: {str(e)}")
            return False

    async def save_face_data(self, image_data: bytes, face_token: str) -> bool:
        """Save face data and add to Face Set"""
        try:
            # Save data locally using DBManager
            success = await self.db_manager.save_face_data(image_data, face_token)
            if not success:
                return False
            
            # Add to Face Set
            success = await self.add_face_to_face_set(face_token)
            if not success:
                logger.error("Failed to add face to Face Set")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving face data: {str(e)}")
            return False

    async def verify_face(self, image_data: bytes) -> Dict:
        """Main verification flow"""
        # Step 1: Detect face and get face token
        face_token = await self.detect_face(image_data)
        
        # Step 2: Search for similar faces
        matches = await self.search_similar_faces(face_token)
        
        # Step 3: Process results
        status = "success"
        message = "New face registered successfully"
        is_duplicate = False
        confidence = None
        top_matches = []

        if not matches:
            # No matches above threshold - save as new face
            success = await self.save_face_data(image_data, face_token)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to save face data")
        else:
            # Found matches above threshold
            best_match = matches[0]
            is_duplicate = best_match.confidence >= self.confidence_threshold
            confidence = best_match.confidence
            top_matches = matches[:3]  # Store top 3 matches
            
            if is_duplicate:
                status = "duplicate"
                message = "Face match found - access denied"
            else:
                # Not a duplicate, save the new face
                success = await self.save_face_data(image_data, face_token)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to save face data")

        # Return the result dictionary
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