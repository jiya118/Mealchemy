"""
LLM Meal Plan Orchestrator - Simplified flow (no Spoonacular dependency).

Flow per day:
  1. IntelligentPantrySelector  → select 10 ingredients from virtual pantry
  2. LLMRecipeService.suggest_recipe() → {recipe_name, main_ingredients}
  3. _determine_shopping_list()  → ingredients not in pantry (user must buy)
  4. deduct_ingredients()        → reduce virtual pantry for matched items
  5. Accumulate results

Final response shape (per generate_weekly_plan):
  {
    'success': True,
    'meals': [{'day': 'monday', 'recipe_name': '...', 'ingredients_deducted': [...]}, ...],
    'shopping_list': ['item1', 'item2', ...],    # unique across all days
    'pantry_summary': {...},
    'days_generated': 7
  }
"""
import logging
from typing import List, Dict, Any, Optional, Set

from app.services.intelligent_pantry_selector import IntelligentPantrySelector
from app.services.llm_recipe_service import LLMRecipeService

logger = logging.getLogger(__name__)

# Common spices/condiments to not flag as "to buy" even if not in pantry
_COMMON_SPICES: Set[str] = {
    'salt', 'pepper', 'oil', 'olive oil', 'vegetable oil', 'cooking oil',
    'chili powder', 'cumin', 'turmeric', 'coriander', 'paprika',
    'garam masala', 'sugar', 'garlic powder', 'onion powder',
    'soy sauce', 'vinegar', 'baking soda', 'baking powder',
    'yeast', 'cardamom', 'cinnamon', 'cloves', 'bay leaf', 'bay leaves',
    'black pepper', 'red chili', 'dried herbs', 'oregano', 'basil', 'thyme',
    'rosemary', 'mustard seeds', 'fenugreek', 'hing', 'asafoetida',
}


class LLMMealPlanOrchestrator:
    """
    Orchestrates LLM-powered meal plan generation.

    No Spoonacular calls in the generation loop \u2014 the LLM owns ingredient knowledge.
    """

    DAYS_OF_WEEK = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    def __init__(
        self,
        pantry_items: List[Dict[str, Any]],
        llm_service: LLMRecipeService,
        # legacy params accepted but unused \u2014 keeps existing callers compatible
        recipe_cache_manager=None,
        spoonacular_client=None,
    ):
        self.pantry_selector = IntelligentPantrySelector(pantry_items)
        self.llm = llm_service

        logger.info(
            f"LLMMealPlanOrchestrator ready \u2014 {len(pantry_items)} pantry items"
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _determine_shopping_list(
        self,
        main_ingredients: List[str],
        available_pantry_names: List[str],
    ) -> List[str]:
        """
        Compare recipe's main_ingredients against current virtual pantry.

        Returns the subset that is NOT in the pantry (user needs to buy),
        excluding common spices/condiments.

        Matching is case-insensitive and uses substring containment:
        e.g. pantry has "Basmati Rice" \u2192 matches "rice" from LLM ingredient list.
        """
        pantry_lower = [name.lower() for name in available_pantry_names]
        to_buy = []

        for ingredient in main_ingredients:
            ing_lower = ingredient.lower().strip()

            # Skip common spices
            if any(spice in ing_lower for spice in _COMMON_SPICES):
                continue

            # Check if pantry has it (fuzzy: either string contains the other)
            in_pantry = any(
                ing_lower in pantry_name or pantry_name in ing_lower
                for pantry_name in pantry_lower
            )

            if not in_pantry:
                to_buy.append(ingredient)

        return to_buy

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def generate_weekly_plan(
        self,
        days: int = 7,
        diet_type: str = 'standard',
        servings: int = 2,
    ) -> Dict[str, Any]:
        """
        Generate a multi-day meal plan via LLM.

        Returns:
            success, meals, shopping_list, pantry_summary, days_generated
        """
        logger.info(f"=== Generating {days}-day LLM meal plan (diet={diet_type}) ===")

        meals: List[Dict[str, Any]] = []
        all_shopping: List[str] = []          # deduplicated across days
        shopping_set: Set[str] = set()
        used_recipe_names: List[str] = []

        for day_num in range(days):
            day_name = self.DAYS_OF_WEEK[day_num % 7]
            logger.info(f"--- Day {day_num + 1}: {day_name} ---")

            # 1. Select ingredients for today from virtual pantry
            selected_ingredients = self.pantry_selector.select_ingredients_for_day(
                max_items=10,
                target_vegetables=6,
                target_proteins=2,
                target_carbs=2,
            )

            if not selected_ingredients:
                logger.warning(f"No ingredients left for {day_name}, stopping")
                break

            logger.info(
                f"Selected {len(selected_ingredients)} ingredients: "
                f"{', '.join(selected_ingredients[:5])}..."
            )

            # 2. Ask LLM for a recipe
            try:
                llm_result = await self.llm.suggest_recipe(
                    available_ingredients=selected_ingredients,
                    diet_type=diet_type,
                    meal_type='dinner',
                    exclude_recipes=used_recipe_names,
                )
            except Exception as e:
                logger.error(f"LLM failed for {day_name}: {e}")
                continue

            recipe_name = llm_result['recipe_name']
            main_ingredients = llm_result['main_ingredients']

            logger.info(f"LLM suggested: '{recipe_name}' ({len(main_ingredients)} ingredients)")

            # 3. Determine what the user must buy
            to_buy = self._determine_shopping_list(
                main_ingredients=main_ingredients,
                available_pantry_names=selected_ingredients,
            )

            # 4. Deduct matching ingredients from virtual pantry
            deducted = self.pantry_selector.deduct_ingredients(
                recipe_ingredients=[
                    {'name': ing, 'quantity': 1, 'unit': ''}
                    for ing in main_ingredients
                    if ing not in to_buy         # only deduct what we have
                ],
                servings=servings,
            )

            # 5. Accumulate unique shopping items
            for item in to_buy:
                if item.lower() not in shopping_set:
                    shopping_set.add(item.lower())
                    all_shopping.append(item)

            meals.append({
                'day': day_name,
                'recipe_name': recipe_name,
                'main_ingredients': main_ingredients,
                'ingredients_to_buy': to_buy,
                'ingredients_deducted': [d['name'] for d in deducted],
                # kept for DB / CRUD compatibility
                'recipe_id': None,
                'ready_in_minutes': None,
                'servings': servings,
            })

            used_recipe_names.append(recipe_name)

            logger.info(
                f"\u2713 {day_name}: '{recipe_name}' | "
                f"buy={to_buy} | deducted={len(deducted)} items | "
                f"pantry remaining={self.pantry_selector.get_remaining_items_count()}"
            )

        logger.info(f"=== Plan complete: {len(meals)}/{days} days ===")

        return {
            'success': len(meals) > 0,
            'meals': meals,
            'shopping_list': [{'name': item} for item in all_shopping],
            'pantry_summary': self.pantry_selector.get_summary(),
            'days_generated': len(meals),
        }

    async def generate_single_meal(
        self,
        diet_type: str = 'standard',
        servings: int = 2,
        meal_type: str = 'dinner',
    ) -> Dict[str, Any]:
        """
        Generate a single meal suggestion.

        Returns:
            success, recipe_name, ingredients_to_buy, [error]
        """
        logger.info(f"Generating single {meal_type} (diet={diet_type})")

        selected_ingredients = self.pantry_selector.select_ingredients_for_day(max_items=10)

        if not selected_ingredients:
            return {'success': False, 'error': 'No ingredients available in pantry'}

        try:
            llm_result = await self.llm.suggest_recipe(
                available_ingredients=selected_ingredients,
                diet_type=diet_type,
                meal_type=meal_type,
            )

            recipe_name = llm_result['recipe_name']
            main_ingredients = llm_result['main_ingredients']

            to_buy = self._determine_shopping_list(
                main_ingredients=main_ingredients,
                available_pantry_names=selected_ingredients,
            )

            return {
                'success': True,
                'recipe_name': recipe_name,
                'recipe_id': None,
                'cooking_time': None,
                'main_ingredients': main_ingredients,
                'ingredients_to_buy': to_buy,
            }

        except Exception as e:
            logger.error(f"Single meal generation failed: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}