from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from contextlib import contextmanager
from config import MONGO_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = None
            cls._instance.db = None
        return cls._instance
    
    def __init__(self):
        if not self.client:
            self.connect()
    
    def connect(self) -> None:
        try:
            self.client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            self.db = self.client.broadcast_bot
            # Test connection
            self.client.server_info()
            logger.info("✅ MongoDB connected successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise
    
    def get_database(self) -> Database:
        if not self.client or not self.db:
            self.connect()
        return self.db
    
    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
    
    @contextmanager
    def session(self):
        try:
            yield self.get_database()
        except Exception as e:
            logger.error(f"Database operation failed: {e}")
            raise
        finally:
            # Keep connection open for reuse, only close on program termination
            pass

# Global database instance
db_manager = DatabaseManager()