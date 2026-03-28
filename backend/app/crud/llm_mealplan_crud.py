"""
CRUD operations for LLM-generated meal plans.

Stores plans in the 'llm_meal_plans' MongoDB collection.
Schema is deliberately lightweight — raw meal dicts from the orchestrator are stored as-is.
"""
from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class LLMMealPlanCRUD:
    """CRUD for LLM-generated meal plans."""

    COLLECTION_NAME = "llm_meal_plans"

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _to_object_id(id_str: str) -> ObjectId:
        """Convert string to ObjectId or raise ValueError."""
        try:
            return ObjectId(id_str)
        except Exception:
            raise ValueError(f"Invalid plan ID: {id_str!r}")

    @staticmethod
    def _serialize(doc: dict) -> dict:
        """Convert ObjectId → str so the document is JSON-serializable."""
        if doc and "_id" in doc:
            doc["id"] = str(doc.pop("_id"))
        return doc

    # -------------------------------------------------------------------------
    # Write
    # -------------------------------------------------------------------------

    async def create(
        self,
        meals: List[Dict[str, Any]],
        shopping_list: List[str],
        pantry_summary: Dict[str, Any],
        days_generated: int,
        diet_type: str,
        servings: int,
    ) -> Dict[str, Any]:
        """
        Persist a newly generated LLM meal plan.

        Args:
            meals: List of meal dicts produced by the orchestrator.
            shopping_list: List of ingredient name strings to buy.
            pantry_summary: Summary dict from IntelligentPantrySelector.
            days_generated: How many days were successfully planned.
            diet_type: Diet string ("vegetarian", "vegan", …).
            servings: Servings per meal.

        Returns:
            Saved document as dict, including top-level ``id`` field.
        """
        now = datetime.utcnow()

        # Strip bulky 'full_recipe' blobs before storing to keep docs small.
        slim_meals = []
        for m in meals:
            slim_meals.append({
                "day": m.get("day"),
                "recipe_id": m.get("recipe_id"),
                "recipe_name": m.get("recipe_name"),
                "ready_in_minutes": m.get("ready_in_minutes"),
                "servings": m.get("servings", servings),
                "ingredients_deducted": m.get("ingredients_deducted", []),
                "is_completed": False,
                "completed_at": None,
            })

        doc = {
            "meals": slim_meals,
            "shopping_list": shopping_list,
            "pantry_summary": pantry_summary,
            "days_generated": days_generated,
            "diet_type": diet_type,
            "servings": servings,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

        result = await self.collection.insert_one(doc)
        created = await self.collection.find_one({"_id": result.inserted_id})

        logger.info(f"LLM meal plan created: {result.inserted_id}")
        return self._serialize(created)

    async def update_day(
        self,
        plan_id: str,
        day: str,
        new_meal: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Replace the meal entry for a given day with a new one.

        Returns the updated plan, or None if not found.
        """
        plan = await self.collection.find_one({"_id": self._to_object_id(plan_id)})
        if not plan:
            return None

        meals = plan.get("meals", [])
        replaced = False

        for i, m in enumerate(meals):
            if m.get("day") == day:
                meals[i] = {
                    "day": day,
                    "recipe_id": new_meal.get("recipe_id"),
                    "recipe_name": new_meal.get("recipe_name"),
                    "ready_in_minutes": new_meal.get("ready_in_minutes"),
                    "servings": new_meal.get("servings"),
                    "ingredients_deducted": new_meal.get("ingredients_deducted", []),
                    "is_completed": False,
                    "completed_at": None,
                }
                replaced = True
                break

        if not replaced:
            # Day did not exist yet — append it
            meals.append({
                "day": day,
                "recipe_id": new_meal.get("recipe_id"),
                "recipe_name": new_meal.get("recipe_name"),
                "ready_in_minutes": new_meal.get("ready_in_minutes"),
                "servings": new_meal.get("servings"),
                "ingredients_deducted": new_meal.get("ingredients_deducted", []),
                "is_completed": False,
                "completed_at": None,
            })

        await self.collection.update_one(
            {"_id": self._to_object_id(plan_id)},
            {"$set": {"meals": meals, "updated_at": datetime.utcnow()}},
        )

        updated = await self.collection.find_one({"_id": self._to_object_id(plan_id)})
        return self._serialize(updated)

    async def mark_meal_complete(
        self,
        plan_id: str,
        day: str,
        meal_type: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Mark a specific day's meal as completed.

        ``meal_type`` is stored for future multi-meal-per-day support but
        currently the plan stores one meal per day, so we match on ``day``.

        Returns the updated plan, or None if not found.
        """
        plan = await self.collection.find_one({"_id": self._to_object_id(plan_id)})
        if not plan:
            return None

        meals = plan.get("meals", [])
        marked = False

        for m in meals:
            if m.get("day") == day:
                m["is_completed"] = True
                m["completed_at"] = datetime.utcnow().isoformat()
                marked = True
                break

        if not marked:
            return None

        await self.collection.update_one(
            {"_id": self._to_object_id(plan_id)},
            {"$set": {"meals": meals, "updated_at": datetime.utcnow()}},
        )

        updated = await self.collection.find_one({"_id": self._to_object_id(plan_id)})
        return self._serialize(updated)

    # -------------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------------

    async def get_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Return plan by ID, or None if not found."""
        doc = await self.collection.find_one({"_id": self._to_object_id(plan_id)})
        return self._serialize(doc) if doc else None

    # -------------------------------------------------------------------------
    # Delete
    # -------------------------------------------------------------------------

    async def delete(self, plan_id: str) -> bool:
        """Delete plan. Returns True if deleted, False if not found."""
        result = await self.collection.delete_one({"_id": self._to_object_id(plan_id)})
        deleted = result.deleted_count > 0
        logger.info(f"LLM meal plan {'deleted' if deleted else 'not found'}: {plan_id}")
        return deleted


def get_llm_meal_plan_crud(collection: AsyncIOMotorCollection) -> LLMMealPlanCRUD:
    """Factory function — use as FastAPI dependency."""
    return LLMMealPlanCRUD(collection)
