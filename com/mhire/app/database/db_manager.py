import os
import json
import logging
import aiofiles
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from com.mhire.app.config.config import Config

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self):
        self.config = Config()
        self.tokens_path = self.config.face_tokens
        self.faceset_metadata_path = self.config.faceset_metadata
        self.MAX_FACESET_CAPACITY = 1000
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.tokens_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.faceset_metadata_path), exist_ok=True)

    async def get_faceset_metadata(self) -> Dict[str, Dict]:
        """Load FaceSet metadata from local storage"""
        try:
            if not os.path.exists(self.faceset_metadata_path):
                async with aiofiles.open(self.faceset_metadata_path, 'w') as f:
                    await f.write(json.dumps({}))
                return {}
                
            async with aiofiles.open(self.faceset_metadata_path, 'r') as f:
                content = await f.read()
                return json.loads(content) if content else {}
                
        except Exception as e:
            logger.error(f"Error loading FaceSet metadata: {str(e)}")
            return {}

    async def save_faceset_metadata(self, metadata: Dict[str, Dict]) -> bool:
        """Save FaceSet metadata to local storage"""
        try:
            async with aiofiles.open(self.faceset_metadata_path, 'w') as f:
                await f.write(json.dumps(metadata))
            return True
        except Exception as e:
            logger.error(f"Error saving FaceSet metadata: {str(e)}")
            return False

    async def get_face_tokens(self) -> Dict[str, str]:
        """
        Get all face tokens and their associated FaceSet IDs
        Returns:
            Dict[str, str]: Dictionary mapping face_token to faceset_id
        """
        try:
            if not os.path.exists(self.tokens_path):
                async with aiofiles.open(self.tokens_path, 'w') as f:
                    await f.write(json.dumps({}))
                return {}
                
            async with aiofiles.open(self.tokens_path, 'r') as f:
                content = await f.read()
                return json.loads(content) if content else {}
                
        except Exception as e:
            logger.error(f"Error loading face tokens: {str(e)}")
            return {}

    async def save_face_token(self, face_token: str, faceset_id: str) -> bool:
        """
        Save a face token and its associated FaceSet ID
        Args:
            face_token (str): The face token to save
            faceset_id (str): The ID of the FaceSet containing this token
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            tokens = await self.get_face_tokens()
            tokens[face_token] = faceset_id
            
            async with aiofiles.open(self.tokens_path, 'w') as f:
                await f.write(json.dumps(tokens))
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving face token: {str(e)}")
            return False

    async def find_available_faceset(self) -> Optional[Tuple[str, int]]:
        """
        Find a FaceSet with available capacity
        Returns:
            Optional[Tuple[str, int]]: Tuple of (faceset_id, current_count) if found, None if not
        """
        try:
            metadata = await self.get_faceset_metadata()
            
            for faceset_id, data in metadata.items():
                if data.get('face_count', 0) < self.MAX_FACESET_CAPACITY:
                    return faceset_id, data.get('face_count', 0)
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding available FaceSet: {str(e)}")
            return None

    async def update_faceset_count(self, faceset_id: str, new_count: int) -> bool:
        """Update the face count for a FaceSet"""
        try:
            metadata = await self.get_faceset_metadata()
            if faceset_id in metadata:
                metadata[faceset_id]['face_count'] = new_count
                return await self.save_faceset_metadata(metadata)
            return False
        except Exception as e:
            logger.error(f"Error updating FaceSet count: {str(e)}")
            return False

    async def add_new_faceset(self, faceset_id: str) -> bool:
        """Add a new FaceSet to metadata"""
        try:
            metadata = await self.get_faceset_metadata()
            metadata[faceset_id] = {
                'face_count': 0,
                'created_at': str(datetime.now())
            }
            return await self.save_faceset_metadata(metadata)
        except Exception as e:
            logger.error(f"Error adding new FaceSet: {str(e)}")
            return False