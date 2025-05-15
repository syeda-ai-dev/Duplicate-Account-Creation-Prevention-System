import logging
from motor.motor_asyncio import AsyncIOMotorClient

from com.mhire.app.config.config import Config

logger = logging.getLogger(__name__)

class DBConnection:
    def __init__(self):
        self.config = Config()
        # Initialize MongoDB connection
        self.client = AsyncIOMotorClient(self.config.mongodb_uri)
        self.db = self.client[self.config.mongodb_db]
        self.collection = self.db[self.config.mongodb_collection]

    async def close(self):
        if self.client:
            self.client.close()