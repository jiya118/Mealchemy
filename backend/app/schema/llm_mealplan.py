"""
Schemas for LLM-powered meal planning API.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class DietTypeEnum(str, Enum):
    """Supported diet types."""
    STANDARD = "standard"
    VEGETARIAN = "vegetarian"
    EGGETARIAN = "eggetarian"
    VEGAN = "vegan"
    PESCATARIAN = "pescatarian"
    KETO = "keto"
    PALEO = "paleo"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"


class MealTypeEnum(str, Enum):
    """Meal types."""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class DayOfWeekEnum(str, Enum):
    """Days of the week."""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# ============================================================================
# REQUEST SCHEMAS
# ============================================================================

class LLMMealPlanRequest(BaseModel):
    """Request to generate LLM-powered meal plan."""
    
    days: int = Field(
        default=7,
        ge=1,
        le=14,
        description="Number of days to plan for"
    )
    
    diet_type: DietTypeEnum = Field(
        default=DietTypeEnum.STANDARD,
        description="Dietary restriction"
    )
    
    servings: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Number of servings per meal"
    )
    
    meals_per_day: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of meals per day"
    )


class SingleMealRequest(BaseModel):
    """Request to generate a single meal."""
    
    diet_type: DietTypeEnum = Field(
        default=DietTypeEnum.STANDARD,
        description="Dietary restriction"
    )
    
    servings: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Number of servings"
    )
    
    meal_type: MealTypeEnum = Field(
        default=MealTypeEnum.DINNER,
        description="Type of meal"
    )


class RegenerateDayRequest(BaseModel):
    """Request to regenerate a specific day in plan."""
    
    day: DayOfWeekEnum = Field(
        description="Day to regenerate"
    )


class CompleteMealRequest(BaseModel):
    """Request to mark meal as completed."""
    
    day: DayOfWeekEnum = Field(
        description="Day of the meal"
    )
    
    meal_type: MealTypeEnum = Field(
        default=MealTypeEnum.DINNER,
        description="Type of meal completed"
    )


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class MealResponse(BaseModel):
    """Single meal in the plan."""
    
    day: str = Field(description="Day of the week")
    recipe_id: int = Field(description="Spoonacular recipe ID")
    recipe_name: str = Field(description="Recipe name")
    ready_in_minutes: int = Field(description="Cooking time")
    servings: int = Field(description="Number of servings")
    reason: Optional[str] = Field(None, description="Why this recipe was chosen")


class ShoppingItem(BaseModel):
    """Item in shopping list."""
    
    name: str = Field(description="Ingredient name")
    quantity: Optional[float] = Field(None, description="Quantity needed")
    unit: Optional[str] = Field(None, description="Unit of measurement")


class PantrySummary(BaseModel):
    """Summary of pantry state."""
    
    total_items: int = Field(description="Total items in pantry")
    proteins: List[str] = Field(default_factory=list)
    carbs: List[str] = Field(default_factory=list)
    vegetables: List[str] = Field(default_factory=list)
    expiring_soon: List[Dict[str, Any]] = Field(default_factory=list)


class LLMMealPlanResponse(BaseModel):
    """Response for meal plan generation."""
    
    status: str = Field(description="success or error")
    meal_plan: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Dict of day -> list of recipe names"
    )
    shopping_list: Optional[List[str]] = Field(
        None,
        description="List of items to buy"
    )
    pantry_summary: Optional[PantrySummary] = Field(
        None,
        description="Summary of pantry state"
    )
    days_generated: Optional[int] = Field(
        None,
        description="Number of days successfully generated"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    suggestion: Optional[str] = Field(None, description="Suggestion for fixing error")


class DetailedMealPlanResponse(BaseModel):
    """Detailed meal plan response (with full recipe info)."""
    
    success: bool = Field(description="Whether generation succeeded")
    meals: List[MealResponse] = Field(description="List of meals")
    shopping_list: List[ShoppingItem] = Field(description="Shopping list")
    pantry_summary: PantrySummary = Field(description="Pantry summary")
    days_generated: int = Field(description="Days generated")
    error: Optional[str] = Field(None, description="Error if failed")


class SingleMealResponse(BaseModel):
    """Response for single meal generation."""
    
    success: bool = Field(description="Whether generation succeeded")
    recipe_id: Optional[int] = Field(None, description="Recipe ID")
    recipe_name: Optional[str] = Field(None, description="Recipe name")
    cooking_time: Optional[int] = Field(None, description="Cooking time in minutes")
    ingredients_to_buy: Optional[List[str]] = Field(None, description="Shopping list")
    error: Optional[str] = Field(None, description="Error if failed")


class MealPlanSavedResponse(BaseModel):
    """Response after saving meal plan to database."""
    
    id: str = Field(description="Meal plan ID")
    user_id: str = Field(description="User ID")
    week_start_date: str = Field(description="Start date of plan")
    status: str = Field(description="Plan status")
    meals_count: int = Field(description="Number of meals in plan")
    created_at: str = Field(description="Creation timestamp")