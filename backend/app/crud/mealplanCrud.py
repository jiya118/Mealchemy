"""
CRUD operations for meal plans.
"""
from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging

from app.schema.meal_plan import (
    MealPlanCreate,
    MealPlanResponse,
    MealPlanList,
    MealPlanStatusEnum,
    DayOfWeekEnum,
    MealTypeEnum,
    DayMeals,
    Meal
)

logger = logging.getLogger(__name__)


class MealPlanCRUD:
    """CRUD operations for meal plans."""
    
    COLLECTION_NAME = "meal_plans"
    
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
    def _prepare_response(plan: dict) -> dict:
        """Prepare database document for response."""
        if plan:
            plan["_id"] = str(plan["_id"])
        return plan
    
    async def create(
        self,
        weekly_meals: List[DayMeals],
        shopping_list: List[Dict[str, Any]],
        expiry_warnings: List[str],
        config: Dict[str, Any]
    ) -> MealPlanResponse:
        """
        Create a new meal plan.
        
        Args:
            weekly_meals: List of daily meals
            shopping_list: Aggregated shopping list
            expiry_warnings: Expiry warnings
            config: Meal plan configuration
            
        Returns:
            Created meal plan
        """
        now = datetime.utcnow()
        today = date.today()
        
        # Find next Monday
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        week_start = today + timedelta(days=days_until_monday)
        
        plan_dict = {
            "user_id": None,  # For future multi-user support
            "week_start_date": week_start,
            "status": MealPlanStatusEnum.ACTIVE.value,
            "config": config,
            "meals": [meal.model_dump() for meal in weekly_meals],
            "aggregated_shopping_list": shopping_list,
            "expiry_warnings": expiry_warnings,
            "created_at": now,
            "updated_at": now
        }
        
        result = await self.collection.insert_one(plan_dict)
        created_plan = await self.collection.find_one({"_id": result.inserted_id})
        
        return MealPlanResponse(**self._prepare_response(created_plan))
    
    async def get_by_id(self, plan_id: str) -> Optional[MealPlanResponse]:
        """
        Get a meal plan by ID.
        
        Args:
            plan_id: Meal plan ID
            
        Returns:
            Meal plan if found, None otherwise
        """
        plan = await self.collection.find_one({"_id": self._object_id(plan_id)})
        
        if plan:
            return MealPlanResponse(**self._prepare_response(plan))
        return None
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> MealPlanList:
        """
        Get all meal plans with pagination.
        
        Args:
            skip: Number of items to skip
            limit: Maximum number of items to return
            status: Filter by status
            
        Returns:
            Paginated list of meal plans
        """
        query: Dict[str, Any] = {}
        
        if status:
            query["status"] = status
        
        # Get total count
        total = await self.collection.count_documents(query)
        
        # Get paginated items
        cursor = self.collection.find(query).sort(
            "created_at", -1
        ).skip(skip).limit(limit)
        
        items = []
        async for plan in cursor:
            items.append(MealPlanResponse(**self._prepare_response(plan)))
        
        # Calculate pagination metadata
        page = (skip // limit) + 1 if limit > 0 else 1
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        
        return MealPlanList(
            items=items,
            total=total,
            page=page,
            page_size=limit,
            total_pages=total_pages
        )
    
    async def update_meal(
        self,
        plan_id: str,
        day: DayOfWeekEnum,
        meal_type: MealTypeEnum,
        new_meal: Meal
    ) -> Optional[MealPlanResponse]:
        """
        Update a specific meal in the plan.
        
        Args:
            plan_id: Meal plan ID
            day: Day of week
            meal_type: Type of meal
            new_meal: New meal data
            
        Returns:
            Updated meal plan if found, None otherwise
        """
        # Find the plan
        plan = await self.collection.find_one({"_id": self._object_id(plan_id)})
        
        if not plan:
            return None
        
        # Update the specific meal
        updated = False
        for day_meals in plan["meals"]:
            if day_meals["day"] == day.value:
                for i, meal in enumerate(day_meals["meals"]):
                    if meal["meal_type"] == meal_type.value:
                        day_meals["meals"][i] = new_meal.model_dump()
                        updated = True
                        break
                break
        
        if not updated:
            return None
        
        # Update timestamp
        plan["updated_at"] = datetime.utcnow()
        
        # Save back to database
        await self.collection.replace_one(
            {"_id": self._object_id(plan_id)},
            plan
        )
        
        return MealPlanResponse(**self._prepare_response(plan))
    
    async def complete_meal(
        self,
        plan_id: str,
        day: DayOfWeekEnum,
        meal_type: MealTypeEnum
    ) -> Optional[MealPlanResponse]:
        """
        Mark a meal as completed.
        
        Args:
            plan_id: Meal plan ID
            day: Day of week
            meal_type: Type of meal
            
        Returns:
            Updated meal plan if found, None otherwise
        """
        # Find the plan
        plan = await self.collection.find_one({"_id": self._object_id(plan_id)})
        
        if not plan:
            return None
        
        # Mark meal as completed
        completed = False
        for day_meals in plan["meals"]:
            if day_meals["day"] == day.value:
                for meal in day_meals["meals"]:
                    if meal["meal_type"] == meal_type.value:
                        meal["is_completed"] = True
                        meal["completed_at"] = datetime.utcnow()
                        completed = True
                        break
                break
        
        if not completed:
            return None
        
        # Update timestamp
        plan["updated_at"] = datetime.utcnow()
        
        # Save back to database
        await self.collection.replace_one(
            {"_id": self._object_id(plan_id)},
            plan
        )
        
        return MealPlanResponse(**self._prepare_response(plan))
    
    async def update_status(
        self,
        plan_id: str,
        status: MealPlanStatusEnum
    ) -> Optional[MealPlanResponse]:
        """
        Update meal plan status.
        
        Args:
            plan_id: Meal plan ID
            status: New status
            
        Returns:
            Updated meal plan if found, None otherwise
        """
        result = await self.collection.find_one_and_update(
            {"_id": self._object_id(plan_id)},
            {
                "$set": {
                    "status": status.value,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )
        
        if result:
            return MealPlanResponse(**self._prepare_response(result))
        return None
    
    async def delete(self, plan_id: str) -> bool:
        """
        Delete a meal plan.
        
        Args:
            plan_id: Meal plan ID
            
        Returns:
            True if deleted, False if not found
        """
        result = await self.collection.delete_one(
            {"_id": self._object_id(plan_id)}
        )
        return result.deleted_count > 0
    
    async def get_active_plan(self) -> Optional[MealPlanResponse]:
        """
        Get the currently active meal plan.
        
        Returns:
            Active meal plan if exists, None otherwise
        """
        plan = await self.collection.find_one(
            {"status": MealPlanStatusEnum.ACTIVE.value},
            sort=[("created_at", -1)]
        )
        
        if plan:
            return MealPlanResponse(**self._prepare_response(plan))
        return None


def get_meal_plan_crud(collection: AsyncIOMotorCollection) -> MealPlanCRUD:
    """Factory function to create MealPlanCRUD instance."""
    return MealPlanCRUD(collection)


