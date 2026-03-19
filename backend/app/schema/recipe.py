"""
Pydantic schemas for recipe caching.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RecipeSource(str, Enum):
    """Source of the recipe."""
    SPOONACULAR = "spoonacular"
    CUSTOM = "custom"
    USER = "user"


class SimpleIngredient(BaseModel):
    """Lightweight ingredient for LLM consumption."""
    name: str
    quantity: float
    unit: str


class CachedRecipe(BaseModel):
    """Recipe stored in cache database."""
    recipe_id: str  # e.g., "spoon_123456"
    name: str
    source: RecipeSource = RecipeSource.SPOONACULAR
    
    # For cache matching
    ingredients_simple: List[str]  # ["lentils", "tomatoes", "garlic"]
    ingredients_hash: str  # "gar_len_tom" (alphabetically sorted)
    
    # Lightweight data for LLM
    ingredients_summary: List[SimpleIngredient]
    
    # Full recipe data (not sent to LLM)
    full_recipe: dict  # Complete Spoonacular response
    
    # Metadata
    diet_types: List[str] = []  # ["vegetarian", "vegan"]
    meal_types: List[str] = []  # ["lunch", "dinner"]
    cuisine: Optional[str] = None
    ready_in_minutes: int = 30
    servings: int = 2
    
    # Usage tracking for diversity
    times_used: int = 0
    last_used_date: Optional[datetime] = None
    
    # Quality metrics
    user_rating: Optional[float] = None
    
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "recipe_id": "spoon_123456",
                "name": "Lentil Curry",
                "source": "spoonacular",
                "ingredients_simple": ["lentils", "tomatoes", "garlic"],
                "ingredients_hash": "gar_len_tom",
                "ingredients_summary": [
                    {"name": "lentils", "quantity": 200, "unit": "g"}
                ],
                "full_recipe": {},
                "diet_types": ["vegetarian"],
                "meal_types": ["dinner"],
                "times_used": 3,
                "last_used_date": "2026-03-10T00:00:00"
            }
        }
    }


class CachedRecipeInDB(CachedRecipe):
    """Recipe as stored in database."""
    id: str = Field(..., alias="_id")
    
    model_config = {
        "populate_by_name": True
    }


class CachedRecipeResponse(CachedRecipeInDB):
    """Recipe API response."""
    pass


class LLMRecipeCandidate(BaseModel):
    """Lightweight recipe format for LLM."""
    id: str  # recipe_id for reference
    name: str
    needs: List[SimpleIngredient]  # Just ingredients, no full recipe
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "spoon_123456",
                "name": "Lentil Curry",
                "needs": [
                    {"name": "lentils", "quantity": 200, "unit": "g"},
                    {"name": "tomatoes", "quantity": 3, "unit": "pieces"}
                ]
            }
        }
    }


class LLMPantryItem(BaseModel):
    """Lightweight pantry format for LLM."""
    name: str
    qty: float
    unit: str
    expires: Optional[str] = None  # ISO date string or null
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "lentils",
                "qty": 500,
                "unit": "g",
                "expires": None
            }
        }
    }


class LLMDayPlan(BaseModel):
    """Single day's plan from LLM."""
    recipe_id: str
    reasoning: str
    shopping_needed: List[SimpleIngredient] = []


class LLMWeeklyPlanResponse(BaseModel):
    """LLM's complete weekly plan response."""
    monday: Optional[LLMDayPlan] = None
    tuesday: Optional[LLMDayPlan] = None
    wednesday: Optional[LLMDayPlan] = None
    thursday: Optional[LLMDayPlan] = None
    friday: Optional[LLMDayPlan] = None
    saturday: Optional[LLMDayPlan] = None
    sunday: Optional[LLMDayPlan] = None