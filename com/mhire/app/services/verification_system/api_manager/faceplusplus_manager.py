import logging
import uuid
import time
import asyncio
from typing import Dict, List, Optional
import requests
import json
from datetime import datetime, timedelta
from collections import deque

from fastapi import HTTPException

from com.mhire.app.config.config import Config
from com.mhire.app.services.verification_system.face_verification.face_verification_schema import ErrorResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window  # in seconds
        self.requests = deque()

    async def acquire(self):
        now = datetime.now()
        # Remove expired timestamps
        while self.requests and (now - self.requests[0]) > timedelta(seconds=self.time_window):
            self.requests.popleft()
        
        # If we've hit the limit, wait
        if len(self.requests) >= self.max_requests:
            wait_time = (self.requests[0] + timedelta(seconds=self.time_window) - now).total_seconds()
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                return await self.acquire()
        
        self.requests.append(now)

class FacePlusPlusManager:
    def __init__(self):
        self.config = Config()
        self.api_key = self.config.fpp_api_key
        self.api_secret = self.config.fpp_api_secret
        self.detect_url = self.config.fpp_detect
        self.search_url = self.config.fpp_search
        self.create_url = self.config.fpp_create
        self.add_url = self.config.fpp_add
        self.get_detail_url = self.config.fpp_get_detail
        
        # Rate limiting settings
        self.rate_limiter = RateLimiter(max_requests=10, time_window=1)  # 10 requests per second
        self.max_retries = 3
        self.base_delay = 2  # Base delay in seconds

        if not all([self.api_key, self.api_secret]):
            error = ErrorResponse(status_code=500, detail="Face++ API credentials not configured")
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    def _get_base_params(self) -> Dict[str, str]:
        """Get base parameters required for all API calls"""
        return {
            'api_key': self.api_key,
            'api_secret': self.api_secret
        }

    async def _make_request_with_retry(self, url: str, data: Dict, files: Dict = None, operation: str = "") -> Dict:
        """Make request to Face++ API with retries and rate limiting"""
        retry_count = 0
        last_error = None

        while retry_count < self.max_retries:
            try:
                # Wait for rate limiter
                await self.rate_limiter.acquire()

                safe_data = {k: v for k, v in data.items() if k not in ['api_key', 'api_secret']}
                logger.info(f"Making {operation} request to Face++ API with data: {json.dumps(safe_data)}")
                
                response = requests.post(url, data=data, files=files)
                
                try:
                    result = response.json()
                    
                    # Check for concurrency limit error
                    if response.status_code == 403 and 'error_message' in result and result['error_message'] == 'CONCURRENCY_LIMIT_EXCEEDED':
                        retry_count += 1
                        delay = self.base_delay * (2 ** retry_count)  # Exponential backoff
                        logger.warning(f"Concurrency limit exceeded. Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                        continue
                    
                    if response.status_code != 200:
                        error = ErrorResponse(
                            status_code=response.status_code,
                            detail=f"{operation} failed: {json.dumps(result)}"
                        )
                        raise HTTPException(status_code=error.status_code, detail=error.dict())
                        
                    if 'error_message' in result:
                        error = ErrorResponse(
                            status_code=400,
                            detail=f"{operation} failed: {result['error_message']}"
                        )
                        raise HTTPException(status_code=error.status_code, detail=error.dict())
                        
                    return result
                    
                except json.JSONDecodeError:
                    error = ErrorResponse(
                        status_code=500,
                        detail=f"Invalid response from Face++ API in {operation}"
                    )
                    raise HTTPException(status_code=error.status_code, detail=error.dict())
                    
            except requests.RequestException as e:
                last_error = e
                retry_count += 1
                if retry_count < self.max_retries:
                    delay = self.base_delay * (2 ** retry_count)
                    logger.warning(f"Request failed. Retrying in {delay} seconds... Error: {str(e)}")
                    await asyncio.sleep(delay)
                else:
                    error = ErrorResponse(
                        status_code=503,
                        detail=f"API request failed in {operation} after {self.max_retries} retries: {str(last_error)}"
                    )
                    raise HTTPException(status_code=error.status_code, detail=error.dict())

        # If we've exhausted all retries
        error = ErrorResponse(
            status_code=503,
            detail=f"API request failed in {operation} after {self.max_retries} retries: {str(last_error)}"
        )
        raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def create_new_faceset(self) -> str:
        """Create a new FaceSet"""
        try:
            new_outer_id = f"faceset_{uuid.uuid4().hex[:8]}"
            data = {
                **self._get_base_params(),
                'outer_id': new_outer_id,
                'display_name': new_outer_id,
                'tags': 'face_verification'
            }
            
            result = await self._make_request_with_retry(
                self.create_url,
                data=data,
                operation="create_faceset"
            )
            
            if result and result.get('faceset_token'):
                logger.info(f"Successfully created new FaceSet: {new_outer_id}")
                return new_outer_id
                
            error = ErrorResponse(
                status_code=500,
                detail="Failed to create FaceSet: Invalid response format"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
            
        except HTTPException:
            raise
        except Exception as e:
            error = ErrorResponse(
                status_code=500,
                detail=f"Failed to create FaceSet: {str(e)}"
            )
            logger.error(error.detail)
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def add_face_to_faceset(self, face_token: str, outer_id: str) -> bool:
        """Add a face token to a specific FaceSet"""
        try:
            data = {
                **self._get_base_params(),
                'face_tokens': face_token,
                'outer_id': outer_id
            }
            
            result = await self._make_request_with_retry(
                self.add_url,
                data=data,
                operation="add_face"
            )
            
            if result and 'face_added' in result:
                logger.info(f"Successfully added face to FaceSet {outer_id}")
                return True
                
            error = ErrorResponse(
                status_code=500,
                detail="Failed to add face: Invalid response format"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
            
        except HTTPException:
            raise
        except Exception as e:
            error = ErrorResponse(
                status_code=500,
                detail=f"Failed to add face to FaceSet: {str(e)}"
            )
            logger.error(error.detail)
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def detect_face(self, image_data: bytes) -> Optional[str]:
        """Detect face and get face token from Face++ API"""
        try:
            files = {
                'image_file': ('image.jpg', image_data, 'image/jpeg')
            }
            
            result = await self._make_request_with_retry(
                self.detect_url,
                data=self._get_base_params(),
                files=files,
                operation="detect_face"
            )
            
            if not result.get('faces'):
                logger.info("No face detected in the provided image")
                return None
                
            face_token = result['faces'][0]['face_token']
            logger.info(f"Successfully detected face: {face_token}")
            return face_token
            
        except Exception as e:
            logger.error(f"Face detection failed: {str(e)}")
            return None

    async def search_faces(self, face_token: str, outer_id: str, return_count: int = 5) -> List[Dict]:
        """Search for similar faces in a specific FaceSet"""
        try:
            data = {
                **self._get_base_params(),
                'face_token': face_token,
                'outer_id': outer_id,
                'return_result_count': return_count
            }
            
            result = await self._make_request_with_retry(
                self.search_url,
                data=data,
                operation="search_faces"
            )
            
            if result and 'results' in result:
                logger.info(f"Search found {len(result['results'])} matches in FaceSet {outer_id}")
                return result['results']
                
            error = ErrorResponse(
                status_code=500,
                detail="Face search failed: Invalid response format"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
            
        except HTTPException:
            raise
        except Exception as e:
            error = ErrorResponse(
                status_code=500,
                detail=f"Face search failed: {str(e)}"
            )
            logger.error(error.detail)
            raise HTTPException(status_code=error.status_code, detail=error.dict())

    async def get_faceset_detail(self, outer_id: str) -> Dict:
        """Get details of a FaceSet"""
        try:
            data = {
                **self._get_base_params(),
                'outer_id': outer_id
            }
            
            result = await self._make_request_with_retry(
                self.get_detail_url,
                data=data,
                operation="get_faceset_detail"
            )
            
            if result and 'face_count' in result:
                logger.info(f"Got details for FaceSet {outer_id}: {result['face_count']} faces")
                return result
                
            error = ErrorResponse(
                status_code=500,
                detail="Failed to get FaceSet details: Invalid response format"
            )
            raise HTTPException(status_code=error.status_code, detail=error.dict())
            
        except HTTPException:
            raise
        except Exception as e:
            error = ErrorResponse(
                status_code=500,
                detail=f"Failed to get FaceSet details: {str(e)}"
            )
            logger.error(error.detail)
            raise HTTPException(status_code=error.status_code, detail=error.dict())