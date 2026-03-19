"""
Pydantic schemas for meal planning.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


class MealTypeEnum(str, Enum):
    """Types of meals."""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class DietTypeEnum(str, Enum):
    """Dietary preferences."""
    STANDARD = "standard"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    EGGETARIAN = "eggetarian"


class MealPlanStatusEnum(str, Enum):
    """Meal plan status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DayOfWeekEnum(str, Enum):
    """Days of the week."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class RecipeIngredient(BaseModel):
    """Single ingredient in a recipe."""
    name: str
    quantity: float
    unit: str
    from_pantry: bool = False
    pantry_item_id: Optional[str] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "tomatoes",
                "quantity": 3.0,
                "unit": "pieces",
                "from_pantry": True,
                "pantry_item_id": "507f1f77bcf86cd799439011"
            }
        }
    }


class Recipe(BaseModel):
    """Complete recipe details."""
    id: int
    name: str
    image: Optional[str] = None
    ready_in_minutes: int
    servings: int
    ingredients: List[RecipeIngredient]
    instructions: List[str] = []
    source_url: Optional[str] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 123456,
                "name": "Lentil Curry",
                "image": "https://spoonacular.com/recipeImages/123456.jpg",
                "ready_in_minutes": 30,
                "servings": 2,
                "ingredients": [],
                "instructions": ["Step 1: Heat oil...", "Step 2: Add onions..."],
                "source_url": "https://spoonacular.com/recipes/lentil-curry-123456"
            }
        }
    }


class ShoppingListItem(BaseModel):
    """Item needed for shopping."""
    name: str
    quantity: float
    unit: str
    needed_for: List[str] = []  # e.g., ["monday_dinner", "wednesday_lunch"]
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "heavy cream",
                "quantity": 200.0,
                "unit": "ml",
                "needed_for": ["friday_dinner"]
            }
        }
    }


class Meal(BaseModel):
    """Single meal in the plan."""
    meal_type: MealTypeEnum
    recipe: Recipe
    ingredients_used: List[RecipeIngredient]
    shopping_list: List[ShoppingListItem] = []
    note: Optional[str] = None
    match_score: float = Field(..., ge=0, le=100)
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "meal_type": "dinner",
                "recipe": {},
                "ingredients_used": [],
                "shopping_list": [],
                "note": "Using bell peppers that expire in 2 days",
                "match_score": 85.5,
                "is_completed": False,
                "completed_at": None
            }
        }
    }


class DayMeals(BaseModel):
    """All meals for a single day."""
    day: DayOfWeekEnum
    meals: List[Meal]
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "day": "monday",
                "meals": []
            }
        }
    }


class MealPlanConfig(BaseModel):
    """Configuration for meal plan generation."""
    meals_per_day: int = Field(default=1, ge=1, le=3)
    diet_type: DietTypeEnum = Field(default=DietTypeEnum.STANDARD)
    servings: int = Field(default=1, ge=1, le=10)
    days: int = Field(default=7, ge=1, le=14)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "meals_per_day": 1,
                "diet_type": "vegetarian",
                "servings": 2,
                "days": 7
            }
        }
    }


class MealPlanCreate(BaseModel):
    """Schema for creating a meal plan."""
    meals_per_day: int = Field(default=1, ge=1, le=3)
    diet_type: DietTypeEnum = Field(default=DietTypeEnum.STANDARD)
    servings: int = Field(default=1, ge=1, le=10)
    days: int = Field(default=7, ge=1, le=14)


class MealPlanInDB(BaseModel):
    """Meal plan as stored in database."""
    id: str = Field(..., alias="_id")
    user_id: Optional[str] = None
    week_start_date: date
    status: MealPlanStatusEnum = Field(default=MealPlanStatusEnum.ACTIVE)
    config: MealPlanConfig
    meals: List[DayMeals]
    aggregated_shopping_list: List[ShoppingListItem] = []
    expiry_warnings: List[str] = []
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "user_id": None,
                "week_start_date": "2026-03-17",
                "status": "active",
                "config": {},
                "meals": [],
                "aggregated_shopping_list": [],
                "expiry_warnings": [],
                "created_at": "2026-03-17T10:00:00",
                "updated_at": "2026-03-17T10:00:00"
            }
        }
    }


class MealPlanResponse(MealPlanInDB):
    """Meal plan API response."""
    pass


class MealPlanList(BaseModel):
    """Paginated list of meal plans."""
    items: List[MealPlanResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class RegenerateMealRequest(BaseModel):
    """Request to regenerate a single meal."""
    day: DayOfWeekEnum
    meal_type: MealTypeEnum
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "day": "wednesday",
                "meal_type": "dinner"
            }
        }
    }


class CompleteMealRequest(BaseModel):
    """Request to mark a meal as completed."""
    day: DayOfWeekEnum
    meal_type: MealTypeEnum
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "day": "monday",
                "meal_type": "dinner"
            }
        }
    }