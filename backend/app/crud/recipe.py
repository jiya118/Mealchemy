"""
CRUD operations for recipe cache.
"""
from motor.motor_asyncio import AsyncIOMotorCollection
from bson import ObjectId
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from app.schema.recipe import CachedRecipe, CachedRecipeResponse

logger = logging.getLogger(__name__)


class RecipeCRUD:
    """CRUD operations for recipe cache."""
    
    COLLECTION_NAME = "recipes"
    
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
    def _prepare_response(recipe: dict) -> dict:
        """Prepare database document for response."""
        if recipe:
            recipe["_id"] = str(recipe["_id"])
        return recipe
    
    async def create(self, recipe: CachedRecipe) -> CachedRecipeResponse:
        """
        Save a recipe to cache.
        
        Args:
            recipe: Recipe to cache
            
        Returns:
            Cached recipe
        """
        recipe_dict = recipe.model_dump()
        recipe_dict["created_at"] = datetime.utcnow()
        recipe_dict["updated_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(recipe_dict)
        created_recipe = await self.collection.find_one({"_id": result.inserted_id})
        
        return CachedRecipeResponse(**self._prepare_response(created_recipe))
    
    async def get_by_recipe_id(self, recipe_id: str) -> Optional[CachedRecipeResponse]:
        """
        Get recipe by its recipe_id (e.g., spoon_123456).
        
        Args:
            recipe_id: Recipe identifier
            
        Returns:
            Recipe if found, None otherwise
        """
        recipe = await self.collection.find_one({"recipe_id": recipe_id})
        
        if recipe:
            return CachedRecipeResponse(**self._prepare_response(recipe))
        return None
    
    async def find_by_ingredients(
        self,
        ingredient_hashes: List[str],
        diet_type: Optional[str] = None,
        meal_type: Optional[str] = None,
        limit: int = 20
    ) -> List[CachedRecipeResponse]:
        """
        Find recipes matching ingredient hashes.
        
        Args:
            ingredient_hashes: List of ingredient name hashes to match
            diet_type: Filter by diet type
            meal_type: Filter by meal type
            limit: Maximum recipes to return
            
        Returns:
            List of matching recipes with diversity penalty applied
        """
        # Build query
        query: Dict[str, Any] = {}
        
        # Match recipes that have ANY of the ingredient hashes
        if ingredient_hashes:
            query["ingredients_simple"] = {"$in": ingredient_hashes}
        
        if diet_type and diet_type != "standard":
            query["diet_types"] = diet_type
        
        if meal_type:
            query["meal_types"] = meal_type
        
        # Get candidates
        cursor = self.collection.find(query).limit(limit * 2)  # Get extra for filtering
        
        recipes = []
        async for recipe in cursor:
            recipes.append(CachedRecipeResponse(**self._prepare_response(recipe)))
        
        # Calculate diversity penalty and sort
        scored_recipes = []
        for recipe in recipes:
            # Calculate ingredient overlap
            matching_count = len(set(recipe.ingredients_simple) & set(ingredient_hashes))
            overlap_score = (matching_count / len(recipe.ingredients_simple)) * 100 if recipe.ingredients_simple else 0
            
            # Calculate usage penalty
            usage_penalty = self._calculate_usage_penalty(recipe.last_used_date, recipe.times_used)
            
            final_score = overlap_score - usage_penalty
            scored_recipes.append((recipe, final_score))
        
        # Sort by score descending and return top N
        scored_recipes.sort(key=lambda x: x[1], reverse=True)
        return [recipe for recipe, score in scored_recipes[:limit]]
    
    def _calculate_usage_penalty(self, last_used: Optional[datetime], times_used: int) -> float:
        """
        Calculate penalty based on recent usage.
        
        Args:
            last_used: Last time recipe was used
            times_used: Total times used
            
        Returns:
            Penalty score (0-50)
        """
        if not last_used:
            return 0
        
        days_since_use = (datetime.utcnow() - last_used).days
        
        # Time-based penalty
        if days_since_use < 7:
            time_penalty = 50  # Very heavy penalty for recent use
        elif days_since_use < 14:
            time_penalty = 30
        elif days_since_use < 30:
            time_penalty = 10
        else:
            time_penalty = 0
        
        # Frequency penalty (popular recipes get slight boost)
        frequency_penalty = min(times_used * 2, 10)  # Cap at 10
        
        return time_penalty + frequency_penalty
    
    async def increment_usage(self, recipe_id: str) -> bool:
        """
        Increment usage counter and update last_used_date.
        
        Args:
            recipe_id: Recipe identifier
            
        Returns:
            True if updated, False otherwise
        """
        result = await self.collection.update_one(
            {"recipe_id": recipe_id},
            {
                "$inc": {"times_used": 1},
                "$set": {
                    "last_used_date": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
    
    async def bulk_create(self, recipes: List[CachedRecipe]) -> int:
        """
        Bulk insert recipes into cache.
        
        Args:
            recipes: List of recipes to cache
            
        Returns:
            Number of recipes inserted
        """
        if not recipes:
            return 0
        
        recipe_dicts = []
        for recipe in recipes:
            recipe_dict = recipe.model_dump()
            recipe_dict["created_at"] = datetime.utcnow()
            recipe_dict["updated_at"] = datetime.utcnow()
            recipe_dicts.append(recipe_dict)
        
        result = await self.collection.insert_many(recipe_dicts, ordered=False)
        return len(result.inserted_ids)
    
    async def count_cached_recipes(self) -> int:
        """Get total number of cached recipes."""
        return await self.collection.count_documents({})


def get_recipe_crud(collection: AsyncIOMotorCollection) -> RecipeCRUD:
    """Factory function to create RecipeCRUD instance."""
    return RecipeCRUD(collection)