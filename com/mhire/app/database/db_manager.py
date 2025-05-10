import os
import json
import logging
import aiofiles
from typing import List, Optional
from datetime import datetime
import uuid

from com.mhire.app.config.config import Config

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self):
        self.config = Config()
        self.image_path = self.config.imag_url
        self.tokens_path = self.config.face_tokens
        
        # Ensure directories exist
        os.makedirs(self.image_path, exist_ok=True)
        os.makedirs(os.path.dirname(self.tokens_path), exist_ok=True)

    async def save_image(self, image_data: bytes) -> Optional[str]:
        """
        Save an image to local storage
        Args:
            image_data (bytes): The image data to save
        Returns:
            str: The filename if successful, None otherwise
        """
        try:
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"face_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            image_path = os.path.join(self.image_path, filename)
            
            # Save image
            async with aiofiles.open(image_path, 'wb') as f:
                await f.write(image_data)
            
            return filename
            
        except Exception as e:
            logger.error(f"Error saving image: {str(e)}")
            return None

    async def save_face_token(self, face_token: str) -> bool:
        """
        Save a face token to local storage
        Args:
            face_token (str): The face token to save
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Load existing tokens
            face_tokens = await self.get_face_tokens()
            face_tokens.append(face_token)
            
            # Save updated tokens
            async with aiofiles.open(self.tokens_path, 'w') as f:
                await f.write(json.dumps(face_tokens))
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving face token: {str(e)}")
            return False

    async def get_face_tokens(self) -> List[str]:
        """
        Get all face tokens from local storage
        Returns:
            List[str]: List of face tokens
        """
        try:
            if not os.path.exists(self.tokens_path):
                async with aiofiles.open(self.tokens_path, 'w') as f:
                    await f.write(json.dumps([]))
                return []
                
            async with aiofiles.open(self.tokens_path, 'r') as f:
                content = await f.read()
                return json.loads(content) if content else []
                
        except Exception as e:
            logger.error(f"Error loading face tokens: {str(e)}")
            return []

    async def save_face_data(self, image_data: bytes, face_token: str) -> bool:
        """
        Save both image and face token
        Args:
            image_data (bytes): The image data to save
            face_token (str): The face token to save
        Returns:
            bool: True if both saves are successful, False otherwise
        """
        try:
            # Save image
            filename = await self.save_image(image_data)
            if not filename:
                return False
            
            # Save face token
            success = await self.save_face_token(face_token)
            if not success:
                # If token save fails, we could optionally try to delete the saved image
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving face data: {str(e)}")
            return False