"""
Simplified meal plan response schemas for cleaner API output.
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class SimplifiedShoppingItem(BaseModel):
    """Simple shopping item."""
    name: str
    quantity: float
    unit: str


class SimplifiedMeal(BaseModel):
    """Simplified meal with minimal details."""
    recipe_name: str
    note: Optional[str] = None
    shopping_needed: List[SimplifiedShoppingItem] = []


class SimplifiedDayMeals(BaseModel):
    """Simplified day meals."""
    day: str
    meals: List[SimplifiedMeal]


class SimplifiedMealPlanResponse(BaseModel):
    """Simplified meal plan response."""
    id: str
    week_start_date: str
    meals: List[SimplifiedDayMeals]
    total_shopping_list: List[SimplifiedShoppingItem] = []
    expiry_warnings: List[str] = []
    created_at: datetime
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "69bbc98c379a5eab991bc1bc",
                "week_start_date": "2026-03-23",
                "meals": [
                    {
                        "day": "monday",
                        "meals": [
                            {
                                "recipe_name": "Chicken Stir Fry",
                                "note": "Quick weekday meal, uses expiring chicken",
                                "shopping_needed": []
                            }
                        ]
                    }
                ],
                "total_shopping_list": [
                    {"name": "soy sauce", "quantity": 100, "unit": "ml"}
                ],
                "expiry_warnings": [
                    "Chicken expires in 2 day(s)"
                ],
                "created_at": "2026-03-19T10:00:00"
            }
        }
    }


def convert_to_simplified_response(full_plan) -> SimplifiedMealPlanResponse:
    """Convert full meal plan to simplified format."""
    
    simplified_meals = []
    
    for day_meals in full_plan.meals:
        simplified_day = SimplifiedDayMeals(
            day=day_meals.day.value,
            meals=[
                SimplifiedMeal(
                    recipe_name=meal.recipe.name,
                    note=meal.note,
                    shopping_needed=[
                        SimplifiedShoppingItem(
                            name=item.name,
                            quantity=item.quantity,
                            unit=item.unit
                        )
                        for item in meal.shopping_list
                    ]
                )
                for meal in day_meals.meals
            ]
        )
        simplified_meals.append(simplified_day)
    
    return SimplifiedMealPlanResponse(
        id=full_plan.id,
        week_start_date=str(full_plan.week_start_date),
        meals=simplified_meals,
        total_shopping_list=[
            SimplifiedShoppingItem(
                name=item.name,
                quantity=item.quantity,
                unit=item.unit
            )
            for item in full_plan.aggregated_shopping_list
        ],
        expiry_warnings=full_plan.expiry_warnings,
        created_at=full_plan.created_at
    )