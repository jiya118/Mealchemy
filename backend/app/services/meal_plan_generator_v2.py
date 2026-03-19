"""
Optimized meal plan generator - Cache-first with LLM orchestration.
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
from app.schema.recipe import CachedRecipeResponse, SimpleIngredient
from app.services.recipe_cache_manager import RecipeCacheManager
from app.services.llm_meal_planner import llm_meal_planner
from app.services.pantry_analyzer import PantryAnalyzer
from app.crud.recipe import RecipeCRUD

logger = logging.getLogger(__name__)


class MealPlanGenerator:
    """Optimized meal plan generator using cache and LLM."""
    
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
        Initialize meal plan generator.
        
        Args:
            pantry_items: Current pantry inventory
            recipe_crud: Recipe CRUD instance for cache access
        """
        self.pantry_items = pantry_items
        self.pantry_analyzer = PantryAnalyzer(pantry_items)
        self.cache_manager = RecipeCacheManager(recipe_crud)
        self.config: MealPlanConfig = None
    
    async def generate_weekly_plan(
        self,
        config: MealPlanConfig
    ) -> Tuple[List[DayMeals], List[ShoppingListItem], List[str]]:
        """
        Generate complete weekly meal plan using optimized flow.
        
        Args:
            config: Meal plan configuration
            
        Returns:
            Tuple of (daily_meals, shopping_list, expiry_warnings)
        """
        self.config = config
        logger.info(f"Generating {config.days}-day meal plan (optimized): {config.meals_per_day} meals/day")
        
        # Get expiring items for warnings
        expiring_items = self.pantry_analyzer.get_expiring_items(days=config.days)
        expiry_warnings = self._generate_expiry_warnings(expiring_items)
        
        # Get available ingredients
        available_ingredients = self.pantry_analyzer.get_available_ingredients()
        
        # STEP 1: Get recipe candidates (cache-first)
        logger.info("Getting recipe candidates from cache...")
        recipe_candidates = await self.cache_manager.get_recipe_candidates(
            pantry_ingredients=available_ingredients,
            diet_type=config.diet_type.value,
            meal_type="dinner" if config.meals_per_day == 1 else None,
            target_count=20
        )
        
        if len(recipe_candidates) < 5:
            logger.warning(f"Only {len(recipe_candidates)} candidates - may not have enough variety")
        
        # STEP 2: Let LLM plan the week
        logger.info("Sending to LLM for intelligent planning...")
        llm_plan, error = await llm_meal_planner.plan_week_with_llm(
            pantry_items=self.pantry_items,
            recipe_candidates=recipe_candidates,
            config=config
        )
        
        if not llm_plan or error:
            logger.error(f"LLM planning failed: {error}")
            # Fallback to algorithmic approach
            logger.info("Falling back to algorithmic meal planning")
            return await self._fallback_algorithmic_plan(config, recipe_candidates, expiry_warnings)
        
        # STEP 3: Validate LLM plan
        is_valid, validation_errors = llm_meal_planner.validate_llm_plan(
            llm_plan, recipe_candidates, config.days
        )
        
        if not is_valid:
            logger.warning(f"LLM plan validation failed: {validation_errors}")
            # Try to recover or fallback
            logger.info("Falling back to algorithmic meal planning")
            return await self._fallback_algorithmic_plan(config, recipe_candidates, expiry_warnings)
        
        # STEP 4: Convert LLM plan to our format
        weekly_meals, shopping_list = await self._convert_llm_plan_to_meals(
            llm_plan, recipe_candidates, config
        )
        
        # STEP 5: Update usage statistics for used recipes
        await self._update_recipe_usage(llm_plan)
        
        logger.info(f"Meal plan generation complete using LLM orchestration")
        
        return weekly_meals, shopping_list, expiry_warnings
    
    async def _convert_llm_plan_to_meals(
        self,
        llm_plan,
        recipe_candidates: List[CachedRecipeResponse],
        config: MealPlanConfig
    ) -> Tuple[List[DayMeals], List[ShoppingListItem]]:
        """Convert LLM plan to DayMeals format."""
        recipe_map = {r.recipe_id: r for r in recipe_candidates}
        meal_types = self.MEAL_TYPES_MAP[config.meals_per_day]
        
        weekly_meals = []
        all_shopping_items = []
        
        for day_num in range(config.days):
            day_name = llm_meal_planner.DAY_NAMES[day_num]
            day_plan = getattr(llm_plan, day_name, None)
            
            if not day_plan:
                continue
            
            # Get the recipe
            cached_recipe = recipe_map.get(day_plan.recipe_id)
            if not cached_recipe:
                logger.error(f"Recipe {day_plan.recipe_id} not found in candidates")
                continue
            
            # Convert to our Recipe format
            recipe = self._convert_cached_to_recipe(cached_recipe, config)
            
            # Determine what's from pantry vs shopping
            ingredients_used, shopping_items = self._categorize_ingredients(
                cached_recipe.ingredients_summary,
                day_plan.shopping_needed
            )
            
            # Create meal
            meal = Meal(
                meal_type=meal_types[0],  # For now, use first meal type
                recipe=recipe,
                ingredients_used=ingredients_used,
                shopping_list=shopping_items,
                note=day_plan.reasoning,
                match_score=100.0,  # LLM chose it, so it's a good match
                is_completed=False,
                completed_at=None
            )
            
            # Add to day
            day_meals = DayMeals(
                day=self.DAYS_OF_WEEK[day_num],
                meals=[meal]
            )
            
            weekly_meals.append(day_meals)
            all_shopping_items.extend(shopping_items)
        
        # Aggregate shopping list
        aggregated = self._aggregate_shopping_list(all_shopping_items)
        
        return weekly_meals, aggregated
    
    def _convert_cached_to_recipe(
        self,
        cached: CachedRecipeResponse,
        config: MealPlanConfig
    ) -> Recipe:
        """Convert cached recipe to Recipe format."""
        # Extract from full_recipe data
        full_recipe = cached.full_recipe
        
        # Parse ingredients
        ingredients = []
        for ing_summary in cached.ingredients_summary:
            ingredients.append(RecipeIngredient(
                name=ing_summary.name,
                quantity=ing_summary.quantity,
                unit=ing_summary.unit,
                from_pantry=False  # Will be set later
            ))
        
        # Parse instructions
        instructions = []
        if "analyzedInstructions" in full_recipe and full_recipe["analyzedInstructions"]:
            for instruction_set in full_recipe["analyzedInstructions"]:
                for step in instruction_set.get("steps", []):
                    instructions.append(step.get("step", ""))
        elif "instructions" in full_recipe:
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
    
    def _categorize_ingredients(
        self,
        recipe_ingredients: List[SimpleIngredient],
        shopping_needed: List[SimpleIngredient]
    ) -> Tuple[List[RecipeIngredient], List[ShoppingListItem]]:
        """Categorize ingredients as from pantry or shopping."""
        ingredients_used = []
        shopping_items = []
        
        shopping_names = {ing.name.lower() for ing in shopping_needed}
        
        for ing in recipe_ingredients:
            if ing.name.lower() in shopping_names:
                # Need to buy
                shopping_items.append(ShoppingListItem(
                    name=ing.name,
                    quantity=ing.quantity,
                    unit=ing.unit,
                    needed_for=[]
                ))
            else:
                # From pantry
                is_available, pantry_item = self.pantry_analyzer.check_ingredient_availability(
                    ing.name, ing.quantity
                )
                
                ingredient = RecipeIngredient(
                    name=ing.name,
                    quantity=ing.quantity,
                    unit=ing.unit,
                    from_pantry=is_available,
                    pantry_item_id=pantry_item["id"] if is_available and pantry_item else None
                )
                ingredients_used.append(ingredient)
        
        return ingredients_used, shopping_items
    
    def _aggregate_shopping_list(
        self,
        shopping_items: List[ShoppingListItem]
    ) -> List[ShoppingListItem]:
        """Aggregate shopping items, combining duplicates."""
        aggregated = {}
        
        for item in shopping_items:
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
        """Generate expiry warning messages."""
        warnings = []
        for item_name, days_until_expiry in expiring_items.items():
            if days_until_expiry <= 3:
                warnings.append(f"{item_name.title()} expires in {days_until_expiry} day(s)")
        return warnings
    
    async def _update_recipe_usage(self, llm_plan) -> None:
        """Update usage statistics for recipes used in plan."""
        for day_name in llm_meal_planner.DAY_NAMES:
            day_plan = getattr(llm_plan, day_name, None)
            if day_plan and day_plan.recipe_id:
                await self.cache_manager.recipe_crud.increment_usage(day_plan.recipe_id)
                logger.debug(f"Updated usage for recipe: {day_plan.recipe_id}")
    
    async def _fallback_algorithmic_plan(
        self,
        config: MealPlanConfig,
        recipe_candidates: List[CachedRecipeResponse],
        expiry_warnings: List[str]
    ) -> Tuple[List[DayMeals], List[ShoppingListItem], List[str]]:
        """Fallback to simple algorithmic planning if LLM fails."""
        logger.info("Using algorithmic fallback")
        
        # Simple logic: just pick recipes in order with some randomization
        import random
        
        meal_types = self.MEAL_TYPES_MAP[config.meals_per_day]
        weekly_meals = []
        all_shopping_items = []
        
        # Shuffle candidates for some variety
        shuffled = random.sample(recipe_candidates, min(len(recipe_candidates), config.days * 2))
        
        for day_num in range(config.days):
            if day_num >= len(shuffled):
                break
            
            cached_recipe = shuffled[day_num]
            recipe = self._convert_cached_to_recipe(cached_recipe, config)
            
            # Simple categorization
            ingredients_used = []
            shopping_items = []
            
            for ing in recipe.ingredients:
                is_available, pantry_item = self.pantry_analyzer.check_ingredient_availability(
                    ing.name, ing.quantity
                )
                
                if is_available and pantry_item:
                    ing.from_pantry = True
                    ing.pantry_item_id = pantry_item["id"]
                    ingredients_used.append(ing)
                else:
                    shopping_items.append(ShoppingListItem(
                        name=ing.name,
                        quantity=ing.quantity,
                        unit=ing.unit,
                        needed_for=[]
                    ))
            
            meal = Meal(
                meal_type=meal_types[0],
                recipe=recipe,
                ingredients_used=ingredients_used,
                shopping_list=shopping_items,
                note="Automatically selected",
                match_score=50.0,
                is_completed=False,
                completed_at=None
            )
            
            day_meals = DayMeals(
                day=self.DAYS_OF_WEEK[day_num],
                meals=[meal]
            )
            
            weekly_meals.append(day_meals)
            all_shopping_items.extend(shopping_items)
        
        aggregated = self._aggregate_shopping_list(all_shopping_items)
        
        return weekly_meals, aggregated, expiry_warnings