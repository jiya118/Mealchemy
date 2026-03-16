"""
Database configuration and connection management.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Singleton database manager for MongoDB connection."""
    
    _instance: Optional['DatabaseManager'] = None
    _client: Optional[AsyncIOMotorClient] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.db = None
        self.database_name = None
    
    async def connect(
        self,
        connection_string: str,
        database_name: str,
        **kwargs
    ) -> None:
        """
        Establish connection to MongoDB.
        
        Args:
            connection_string: MongoDB connection URI
            database_name: Name of the database to use
            **kwargs: Additional connection parameters
        """
        try:
            self._client = AsyncIOMotorClient(
                connection_string,
                server_api=ServerApi('1'),
                **kwargs
            )
            # Verify connection
            await self._client.admin.command('ping')
            
            self.db = self._client[database_name]
            self.database_name = database_name
            
            logger.info(f"Successfully connected to MongoDB database: {database_name}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            self._client.close()
            logger.info("Disconnected from MongoDB")
    
    def get_collection(self, collection_name: str):
        """
        Get a collection from the database.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Motor collection instance
        """
        if not self.db:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.db[collection_name]


# Global database manager instance
db_manager = DatabaseManager()


async def get_database():
    """Dependency for getting database instance."""
    return db_manager.db