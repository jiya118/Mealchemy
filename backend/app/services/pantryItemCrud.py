"""
CRUD operations for pantry items.
"""
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ASCENDING, DESCENDING
from bson import ObjectId
from typing import Optional, Any
from datetime import datetime

from schemas.pantry_item import (
    PantryItemCreate,
    PantryItemUpdate,
    PantryItemResponse,
    PantryItemList
)


class PantryItemCRUD:
    """CRUD operations for pantry items."""
    
    COLLECTION_NAME = "pantry_items"
    
    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection
    
    @staticmethod
    def _object_id(id_str: str) -> ObjectId:
        """Convert string ID to ObjectId."""
        try:
            return ObjectId(id_str)
        except Exception:
            raise ValueError(f"Invalid ObjectId: {id_str}")
    
    @staticmethod
    def _prepare_response(item: dict) -> dict:
        """Prepare database document for response."""
        if item:
            item["_id"] = str(item["_id"])
        return item
    
    async def create(self, item_data: PantryItemCreate) -> PantryItemResponse:
        """
        Create a new pantry item.
        
        Args:
            item_data: Pantry item creation data
            
        Returns:
            Created pantry item
        """
        now = datetime.utcnow()
        item_dict = item_data.model_dump()
        item_dict.update({
            "created_at": now,
            "updated_at": now
        })
        
        result = await self.collection.insert_one(item_dict)
        created_item = await self.collection.find_one({"_id": result.inserted_id})
        
        return PantryItemResponse(**self._prepare_response(created_item))
    
    async def get_by_id(self, item_id: str) -> Optional[PantryItemResponse]:
        """
        Get a pantry item by ID.
        
        Args:
            item_id: Pantry item ID
            
        Returns:
            Pantry item if found, None otherwise
        """
        item = await self.collection.find_one({"_id": self._object_id(item_id)})
        
        if item:
            return PantryItemResponse(**self._prepare_response(item))
        return None
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "name",
        sort_order: str = "asc"
    ) -> PantryItemList:
        """
        Get all pantry items with pagination and filtering.
        
        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            category: Filter by category
            search: Search term for name
            sort_by: Field to sort by
            sort_order: Sort order ('asc' or 'desc')
            
        Returns:
            Paginated list of pantry items
        """
        # Build query filter
        query: dict[str, Any] = {}
        
        if category:
            query["category"] = category
        
        if search:
            query["name"] = {"$regex": search, "$options": "i"}
        
        # Determine sort direction
        sort_direction = ASCENDING if sort_order == "asc" else DESCENDING
        
        # Get total count
        total = await self.collection.count_documents(query)
        
        # Get paginated items
        cursor = self.collection.find(query).sort(
            sort_by, sort_direction
        ).skip(skip).limit(limit)
        
        items = []
        async for item in cursor:
            items.append(PantryItemResponse(**self._prepare_response(item)))
        
        # Calculate pagination metadata
        page = (skip // limit) + 1 if limit > 0 else 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        
        return PantryItemList(
            items=items,
            total=total,
            page=page,
            page_size=limit,
            total_pages=total_pages
        )
    
    async def update(
        self,
        item_id: str,
        item_data: PantryItemUpdate
    ) -> Optional[PantryItemResponse]:
        """
        Update a pantry item.
        
        Args:
            item_id: Pantry item ID
            item_data: Updated data
            
        Returns:
            Updated pantry item if found, None otherwise
        """
        # Only include fields that were actually set
        update_data = item_data.model_dump(exclude_unset=True)
        
        if not update_data:
            # No fields to update
            return await self.get_by_id(item_id)
        
        update_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.find_one_and_update(
            {"_id": self._object_id(item_id)},
            {"$set": update_data},
            return_document=True
        )
        
        if result:
            return PantryItemResponse(**self._prepare_response(result))
        return None
    
    async def delete(self, item_id: str) -> bool:
        """
        Delete a pantry item.
        
        Args:
            item_id: Pantry item ID
            
        Returns:
            True if deleted, False if not found
        """
        result = await self.collection.delete_one(
            {"_id": self._object_id(item_id)}
        )
        return result.deleted_count > 0
    
    async def update_quantity(
        self,
        item_id: str,
        quantity_delta: float
    ) -> Optional[PantryItemResponse]:
        """
        Update item quantity by adding a delta value.
        
        Args:
            item_id: Pantry item ID
            quantity_delta: Amount to add (can be negative)
            
        Returns:
            Updated pantry item if found, None otherwise
        """
        result = await self.collection.find_one_and_update(
            {"_id": self._object_id(item_id)},
            {
                "$inc": {"quantity": quantity_delta},
                "$set": {"updated_at": datetime.utcnow()}
            },
            return_document=True
        )
        
        if result:
            return PantryItemResponse(**self._prepare_response(result))
        return None
    
    async def get_expiring_soon(
        self,
        days: int = 7,
        limit: int = 100
    ) -> list[PantryItemResponse]:
        """
        Get items expiring within specified days.
        
        Args:
            days: Number of days to look ahead
            limit: Maximum number of items to return
            
        Returns:
            List of expiring items
        """
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() + timedelta(days=days)
        
        cursor = self.collection.find({
            "expiry_date": {
                "$lte": cutoff_date,
                "$gte": datetime.utcnow()
            }
        }).sort("expiry_date", ASCENDING).limit(limit)
        
        items = []
        async for item in cursor:
            items.append(PantryItemResponse(**self._prepare_response(item)))
        
        return items
    
    async def get_low_stock(
        self,
        threshold: float = 1.0,
        limit: int = 100
    ) -> list[PantryItemResponse]:
        """
        Get items with quantity below threshold.
        
        Args:
            threshold: Quantity threshold
            limit: Maximum number of items to return
            
        Returns:
            List of low stock items
        """
        cursor = self.collection.find({
            "quantity": {"$lte": threshold}
        }).sort("quantity", ASCENDING).limit(limit)
        
        items = []
        async for item in cursor:
            items.append(PantryItemResponse(**self._prepare_response(item)))
        
        return items


def get_pantry_item_crud(collection: AsyncIOMotorCollection) -> PantryItemCRUD:
    """Factory function to create PantryItemCRUD instance."""
    return PantryItemCRUD(collection)