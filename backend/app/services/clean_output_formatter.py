"""
Clean Meal Plan Output Formatter

Formats meal plan in minimal, user-friendly format:
{
  "monday": ["Recipe 1", "Recipe 2"],
  "tuesday": ["Recipe 3"],
  ...
  "shopping_list": ["item1", "item2"]
}
"""
from typing import Dict, Any, List


def format_clean_meal_plan(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert full meal plan result to clean, minimal format.
    
    Args:
        result: Full meal plan from single_shot_meal_planner
        
    Returns:
        {
            "monday": ["Recipe Name 1", "Recipe Name 2"],
            "tuesday": ["Recipe Name"],
            ...
            "shopping_list": ["ingredient1", "ingredient2"],
            "status": "success"
        }
    """
    if not result.get('success'):
        return {
            'status': 'error',
            'error': result.get('error', 'Unknown error'),
            'suggestion': result.get('suggestion', '')
        }
    
    # Build clean daily meals
    clean_plan = {}
    
    for meal_data in result.get('meals', []):
        day = meal_data.get('day')
        recipe_name = meal_data.get('recipe_name')
        
        if day and recipe_name:
            if day not in clean_plan:
                clean_plan[day] = []
            clean_plan[day].append(recipe_name)
    
    # Build clean shopping list (just ingredient names)
    shopping_items = []
    for item in result.get('shopping_list', []):
        name = item.get('name', '')
        quantity = item.get('quantity', '')
        unit = item.get('unit', '')
        
        # Format: "2 cups rice" or just "salt" if no quantity
        if quantity and unit:
            shopping_items.append(f"{quantity} {unit} {name}")
        elif quantity:
            shopping_items.append(f"{quantity} {name}")
        else:
            shopping_items.append(name)
    
    return {
        'status': 'success',
        'meal_plan': clean_plan,
        'shopping_list': shopping_items
    }


def format_detailed_meal_plan(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optional: Format with a bit more detail but still clean.
    
    Returns:
        {
            "days": [
                {
                    "day": "monday",
                    "meals": [{"name": "Recipe", "cook_time": 30}]
                }
            ],
            "shopping_list": [...]
        }
    """
    if not result.get('success'):
        return format_clean_meal_plan(result)
    
    days = []
    
    for meal_data in result.get('meals', []):
        day_entry = {
            'day': meal_data.get('day'),
            'meals': [
                {
                    'name': meal_data.get('recipe_name'),
                    'cook_time_minutes': meal_data.get('ready_in_minutes'),
                    'servings': meal_data.get('servings')
                }
            ]
        }
        days.append(day_entry)
    
    shopping_list = []
    for item in result.get('shopping_list', []):
        shopping_list.append({
            'name': item.get('name'),
            'quantity': item.get('quantity'),
            'unit': item.get('unit'),
            'needed_for': item.get('needed_for', [])
        })
    
    return {
        'status': 'success',
        'days': days,
        'shopping_list': shopping_list,
        'pantry_summary': result.get('pantry_summary', {})
    }