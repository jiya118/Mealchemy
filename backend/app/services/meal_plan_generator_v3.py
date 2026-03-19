"""
Meal plan generator v3 - Agentic approach with LLM tool calling.
"""
from typing import List, Tuple
from datetime import datetime
import logging

from app.schema.meal_plan import (
    MealPlanConfig,
    DayMeals,
    Meal,
    Recipe,
    RecipeIngredient,
    ShoppingListItem,
    MealTypeEnum,
    DayOfWeekEnum
)
from app.schema.pantryItem import PantryItemResponse
from app.services.agentic_meal_planner import AgenticMealPlanner
from app.services.pantry_analyzer import PantryAnalyzer
from app.crud.recipe import RecipeCRUD

logger = logging.getLogger(__name__)


class MealPlanGeneratorV3:
    """Agentic meal plan generator using LLM with tools."""
    
    DAYS_OF_WEEK = [
        DayOfWeekEnum.MONDAY,
        DayOfWeekEnum.TUESDAY,
        DayOfWeekEnum.WEDNESDAY,
        DayOfWeekEnum.THURSDAY,
        DayOfWeekEnum.FRIDAY,
        DayOfWeekEnum.SATURDAY,
        DayOfWeekEnum.SUNDAY
    ]
    
    MEAL_TYPES_MAP = {
        1: [MealTypeEnum.DINNER],
        2: [MealTypeEnum.LUNCH, MealTypeEnum.DINNER],
        3: [MealTypeEnum.BREAKFAST, MealTypeEnum.LUNCH, MealTypeEnum.DINNER]
    }
    
    def __init__(self, pantry_items: List[PantryItemResponse], recipe_crud: RecipeCRUD):
        """
        Initialize agentic meal plan generator.
        
        Args:
            pantry_items: Current pantry inventory
            recipe_crud: Recipe CRUD instance
        """
        self.pantry_items = pantry_items
        self.pantry_analyzer = PantryAnalyzer(pantry_items)
        self.recipe_crud = recipe_crud
        self.config: MealPlanConfig = None
    
    async def generate_weekly_plan(
        self,
        config: MealPlanConfig
    ) -> Tuple[List[DayMeals], List[ShoppingListItem], List[str]]:
        """
        Generate weekly meal plan using agentic LLM.
        
        Args:
            config: Meal plan configuration
            
        Returns:
            Tuple of (daily_meals, shopping_list, expiry_warnings)
        """
        self.config = config
        logger.info(f"Generating {config.days}-day meal plan (agentic v3)")
        
        # Get expiring items for warnings
        expiring_items = self.pantry_analyzer.get_expiring_items(days=config.days)
        expiry_warnings = self._generate_expiry_warnings(expiring_items)
        
        # Initialize agentic planner
        planner = AgenticMealPlanner(self.pantry_items, self.recipe_crud)
        
        # Let LLM plan with tools
        llm_plan, error = await planner.plan_meals(config)
        
        if error or not llm_plan:
            logger.error(f"Agentic planning failed: {error}")
            # Fallback to simple approach
            logger.info("Falling back to simple meal planning")
            return await self._fallback_simple_plan(config, expiry_warnings)
        
        # Convert LLM plan to our format
        weekly_meals, shopping_list = await self._convert_llm_plan_to_meals(
            llm_plan, config
        )
        
        logger.info(f"Agentic meal plan generation complete")
        
        return weekly_meals, shopping_list, expiry_warnings
    
    async def _convert_llm_plan_to_meals(
        self,
        llm_plan: dict,
        config: MealPlanConfig
    ) -> Tuple[List[DayMeals], List[ShoppingListItem]]:
        """Convert LLM plan to DayMeals format."""
        
        meal_types = self.MEAL_TYPES_MAP[config.meals_per_day]
        weekly_meals = []
        all_shopping_items = []
        
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        
        for meal_data in llm_plan.get("meals", []):
            day_name = meal_data.get("day", "").lower()
            
            if day_name not in day_map:
                logger.warning(f"Invalid day: {day_name}")
                continue
            
            day_index = day_map[day_name]
            
            # Get recipe from cache
            recipe_id = meal_data.get("recipe_id")
            cached_recipe = await self.recipe_crud.get_by_recipe_id(recipe_id)
            
            if not cached_recipe:
                logger.error(f"Recipe {recipe_id} not found in cache")
                continue
            
            # Convert to Recipe format
            recipe = self._convert_cached_to_recipe(cached_recipe, config)
            
            # Parse ingredients from LLM plan
            ingredients_used = []
            for ing_data in meal_data.get("ingredients_used", []):
                is_available, pantry_item = self.pantry_analyzer.check_ingredient_availability(
                    ing_data["name"], ing_data.get("quantity", 0)
                )
                
                ingredient = RecipeIngredient(
                    name=ing_data["name"],
                    quantity=ing_data.get("quantity", 0),
                    unit=ing_data.get("unit", ""),
                    from_pantry=is_available,
                    pantry_item_id=pantry_item["id"] if is_available and pantry_item else None
                )
                ingredients_used.append(ingredient)
            
            # Parse shopping list
            shopping_items = []
            for shop_data in meal_data.get("shopping_needed", []):
                shopping_items.append(ShoppingListItem(
                    name=shop_data["name"],
                    quantity=shop_data.get("quantity", 0),
                    unit=shop_data.get("unit", ""),
                    needed_for=[day_name]
                ))
            
            # Create meal
            meal = Meal(
                meal_type=meal_types[0],
                recipe=recipe,
                ingredients_used=ingredients_used,
                shopping_list=shopping_items,
                note=meal_data.get("reasoning", ""),
                match_score=100.0,
                is_completed=False,
                completed_at=None
            )
            
            # Create day meals
            day_meals = DayMeals(
                day=self.DAYS_OF_WEEK[day_index],
                meals=[meal]
            )
            
            weekly_meals.append(day_meals)
            all_shopping_items.extend(shopping_items)
        
        # Aggregate shopping list
        aggregated = self._aggregate_shopping_list(all_shopping_items)
        
        return weekly_meals, aggregated
    
    def _convert_cached_to_recipe(self, cached, config: MealPlanConfig) -> Recipe:
        """Convert cached recipe to Recipe format."""
        
        full_recipe = cached.full_recipe
        
        # Parse ingredients
        ingredients = []
        for ing_summary in cached.ingredients_summary:
            ingredients.append(RecipeIngredient(
                name=ing_summary.name,
                quantity=ing_summary.quantity,
                unit=ing_summary.unit,
                from_pantry=False
            ))
        
        # Parse instructions
        instructions = []
        if "analyzedInstructions" in full_recipe and full_recipe["analyzedInstructions"]:
            for instruction_set in full_recipe["analyzedInstructions"]:
                for step in instruction_set.get("steps", []):
                    if step.get("step"):
                        instructions.append(step.get("step"))
        elif full_recipe.get("instructions"):
            instructions = [full_recipe["instructions"]]
        
        return Recipe(
            id=int(cached.recipe_id.replace("spoon_", "")),
            name=cached.name,
            image=full_recipe.get("image"),
            ready_in_minutes=cached.ready_in_minutes,
            servings=config.servings,
            ingredients=ingredients,
            instructions=instructions,
            source_url=full_recipe.get("sourceUrl")
        )
    
    def _aggregate_shopping_list(self, items: List[ShoppingListItem]) -> List[ShoppingListItem]:
        """Aggregate shopping items."""
        aggregated = {}
        
        for item in items:
            key = f"{item.name.lower()}_{item.unit.lower()}"
            
            if key in aggregated:
                aggregated[key].quantity += item.quantity
                aggregated[key].needed_for.extend(item.needed_for)
            else:
                aggregated[key] = ShoppingListItem(
                    name=item.name,
                    quantity=item.quantity,
                    unit=item.unit,
                    needed_for=item.needed_for.copy()
                )
        
        return list(aggregated.values())
    
    def _generate_expiry_warnings(self, expiring_items: dict) -> List[str]:
        """Generate expiry warnings."""
        warnings = []
        for item_name, days_until_expiry in expiring_items.items():
            if days_until_expiry <= 3:
                warnings.append(f"{item_name.title()} expires in {days_until_expiry} day(s)")
        return warnings
    
    async def _fallback_simple_plan(
        self,
        config: MealPlanConfig,
        expiry_warnings: List[str]
    ) -> Tuple[List[DayMeals], List[ShoppingListItem], List[str]]:
        """Simple fallback if agentic planning fails."""
        
        logger.info("Using simple fallback")
        
        # Get any cached recipes
        cached_recipes = await self.recipe_crud.find_by_ingredients(
            ingredient_hashes=[],
            diet_type=config.diet_type.value if config.diet_type.value != "standard" else None,
            limit=config.days
        )
        
        if not cached_recipes:
            # No recipes at all
            return [], [], expiry_warnings
        
        meal_types = self.MEAL_TYPES_MAP[config.meals_per_day]
        weekly_meals = []
        
        for day_num in range(min(config.days, len(cached_recipes))):
            cached = cached_recipes[day_num]
            recipe = self._convert_cached_to_recipe(cached, config)
            
            # Simple ingredient categorization
            ingredients_used = []
            for ing in recipe.ingredients:
                is_available, pantry_item = self.pantry_analyzer.check_ingredient_availability(
                    ing.name, ing.quantity
                )
                
                if is_available and pantry_item:
                    ing.from_pantry = True
                    ing.pantry_item_id = pantry_item["id"]
                
                ingredients_used.append(ing)
            
            meal = Meal(
                meal_type=meal_types[0],
                recipe=recipe,
                ingredients_used=ingredients_used,
                shopping_list=[],
                note="Simple fallback selection",
                match_score=50.0,
                is_completed=False,
                completed_at=None
            )
            
            day_meals = DayMeals(
                day=self.DAYS_OF_WEEK[day_num],
                meals=[meal]
            )
            
            weekly_meals.append(day_meals)
        
        return weekly_meals, [], expiry_warnings