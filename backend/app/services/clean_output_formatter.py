"""
Clean Meal Plan Output Formatter

Produces the final simplified API response:
{
  "status": "success",
  "meal_plan": {
    "monday": "Recipe Name",
    "tuesday": "Another Recipe",
    ...
  },
  "shopping_list": ["item1", "item2"],
  "days_generated": 7
}
"""
from typing import Dict, Any, List


def format_clean_meal_plan(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert full meal plan result to clean, minimal format.

    meal_plan values are strings (one recipe per day), not lists.
    """
    if not result.get('success'):
        return {
            'status': 'error',
            'error': result.get('error', 'Unknown error'),
            'suggestion': result.get('suggestion', ''),
        }

    # Build {day: recipe_name} mapping
    meal_plan: Dict[str, str] = {}
    for meal in result.get('meals', []):
        day = meal.get('day')
        recipe_name = meal.get('recipe_name')
        if day and recipe_name:
            meal_plan[day] = recipe_name

    # Build flat shopping list (unique ingredient names)
    shopping_items: List[str] = []
    seen = set()
    for item in result.get('shopping_list', []):
        name = item.get('name', '').strip() if isinstance(item, dict) else str(item).strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            shopping_items.append(name)

    return {
        'status': 'success',
        'meal_plan': meal_plan,
        'shopping_list': shopping_items,
        'days_generated': result.get('days_generated', len(meal_plan)),
    }