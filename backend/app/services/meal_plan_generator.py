"""
Meal plan generator - Core orchestrator for intelligent weekly meal planning.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
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
from app.services.spoonacular_client import spoonacular_client
from app.services.llm_client import llm_client
from app.services.pantry_analyzer import PantryAnalyzer
from app.core.settings import settings

logger = logging.getLogger(__name__)


class MealPlanGenerator:
    """Intelligent meal plan generator using pantry inventory and external APIs."""
    
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
    
    def __init__(self, pantry_items: List[PantryItemResponse]):
        """
        Initialize meal plan generator.
        
        Args:
            pantry_items: Current pantry inventory
        """
        self.pantry_analyzer = PantryAnalyzer(pantry_items)
        self.config: Optional[MealPlanConfig] = None
    
    async def generate_weekly_plan(
        self,
        config: MealPlanConfig
    ) -> Tuple[List[DayMeals], List[ShoppingListItem], List[str]]:
        """
        Generate complete weekly meal plan.
        
        Args:
            config: Meal plan configuration
            
        Returns:
            Tuple of (daily_meals, shopping_list, expiry_warnings)
        """
        self.config = config
        logger.info(f"Generating {config.days}-day meal plan: {config.meals_per_day} meals/day, "
                   f"{config.diet_type}, {config.servings} servings")
        
        # Get meal types based on meals per day
        meal_types = self.MEAL_TYPES_MAP[config.meals_per_day]
        
        # Get expiring items for the planning period
        expiring_items = self.pantry_analyzer.get_expiring_items(days=config.days)
        
        # Create virtual pantry for tracking
        virtual_pantry = self.pantry_analyzer.create_virtual_pantry()
        
        weekly_plan: List[DayMeals] = []
        all_shopping_items: List[ShoppingListItem] = []
        expiry_warnings: List[str] = []
        
        # Generate warnings for expiring items
        for item_name, days_until_expiry in expiring_items.items():
            if days_until_expiry <= 3:
                expiry_warnings.append(
                    f"{item_name.title()} expires in {days_until_expiry} day(s)"
                )
        
        # Generate meals for each day
        for day_num in range(config.days):
            day_name = self.DAYS_OF_WEEK[day_num]
            day_meals: List[Meal] = []
            
            logger.info(f"Planning meals for {day_name.value}")
            
            # Generate each meal for the day
            for meal_type in meal_types:
                meal, shopping_items = await self._generate_single_meal(
                    virtual_pantry=virtual_pantry,
                    expiring_items=expiring_items,
                    meal_type=meal_type,
                    day_num=day_num
                )
                
                day_meals.append(meal)
                
                # Track shopping items
                for item in shopping_items:
                    item.needed_for.append(f"{day_name.value}_{meal_type.value}")
                all_shopping_items.extend(shopping_items)
            
            weekly_plan.append(DayMeals(day=day_name, meals=day_meals))
        
        # Aggregate shopping list
        aggregated_shopping = self._aggregate_shopping_list(all_shopping_items)
        
        logger.info(f"Meal plan generation complete. Total shopping items: {len(aggregated_shopping)}")
        
        return weekly_plan, aggregated_shopping, expiry_warnings
    
    async def _generate_single_meal(
        self,
        virtual_pantry: Dict[str, Dict[str, Any]],
        expiring_items: Dict[str, int],
        meal_type: MealTypeEnum,
        day_num: int
    ) -> Tuple[Meal, List[ShoppingListItem]]:
        """
        Generate a single meal.
        
        Args:
            virtual_pantry: Current state of virtual pantry
            expiring_items: Items expiring soon
            meal_type: Type of meal to generate
            day_num: Day number (0-6)
            
        Returns:
            Tuple of (meal, shopping_items)
        """
        # Get available ingredients
        available_ingredients = [
            item["name"] for item in virtual_pantry.values()
            if item["quantity"] > 0
        ]
        
        if not available_ingredients:
            logger.warning(f"No ingredients available for {meal_type.value} on day {day_num}")
            return await self._handle_empty_pantry(meal_type)
        
        # Search for recipes
        best_recipe, match_score = await self._find_best_recipe(
            available_ingredients=available_ingredients,
            expiring_items=expiring_items,
            meal_type=meal_type,
            day_num=day_num
        )
        
        if not best_recipe:
            logger.warning(f"No suitable recipe found for {meal_type.value}")
            return await self._handle_no_recipe_found(meal_type, expiring_items)
        
        # Parse recipe ingredients
        recipe_ingredients = self._parse_recipe_ingredients(best_recipe)
        
        # Identify what's from pantry vs shopping list
        ingredients_used = []
        shopping_list = []
        
        for ingredient in recipe_ingredients:
            # Check if available in virtual pantry
            is_available, pantry_item = self.pantry_analyzer.check_ingredient_availability(
                ingredient.name,
                ingredient.quantity
            )
            
            if is_available and pantry_item:
                ingredient.from_pantry = True
                ingredient.pantry_item_id = pantry_item["id"]
                ingredients_used.append(ingredient)
                
                # Deduct from virtual pantry
                virtual_pantry[ingredient.name.lower()]["quantity"] -= ingredient.quantity
            else:
                shopping_list.append(ShoppingListItem(
                    name=ingredient.name,
                    quantity=ingredient.quantity,
                    unit=ingredient.unit,
                    needed_for=[]
                ))
        
        # Generate helpful note if using expiring items
        note = None
        used_expiring = [
            ing.name for ing in ingredients_used
            if ing.name.lower() in expiring_items
        ]
        
        if used_expiring:
            note = llm_client.generate_shopping_note(
                recipe_name=best_recipe.name,
                missing_items=[item.name for item in shopping_list],
                expiring_items=used_expiring
            )
        
        meal = Meal(
            meal_type=meal_type,
            recipe=best_recipe,
            ingredients_used=ingredients_used,
            shopping_list=shopping_list,
            note=note,
            match_score=match_score
        )
        
        return meal, shopping_list
    
    async def _find_best_recipe(
        self,
        available_ingredients: List[str],
        expiring_items: Dict[str, int],
        meal_type: MealTypeEnum,
        day_num: int
    ) -> Tuple[Optional[Recipe], float]:
        """
        Find the best recipe matching available ingredients.
        
        Args:
            available_ingredients: Ingredients available in pantry
            expiring_items: Items expiring soon
            meal_type: Type of meal
            day_num: Day number for expiry priority
            
        Returns:
            Tuple of (best_recipe, match_score)
        """
        # Prepare ingredient string for API
        ingredients_str = ",".join(available_ingredients[:20])  # Limit to 20 for API
        
        # Determine diet parameter
        diet_param = None if self.config.diet_type.value == "standard" else self.config.diet_type.value
        if self.config.diet_type.value == "eggetarian":
            diet_param = "vegetarian"  # Spoonacular doesn't have eggetarian, use vegetarian
        
        try:
            # Search recipes
            recipe_results = spoonacular_client.search_recipes_by_ingredients(
                ingredients=ingredients_str,
                number=10,
                ranking=1,  # Maximize used ingredients
                diet=diet_param,
                meal_type=meal_type.value
            )
            
            if not recipe_results:
                logger.warning("No recipes found from Spoonacular")
                return None, 0.0
            
            # Score and rank recipes
            scored_recipes: List[Tuple[Dict[str, Any], float]] = []
            
            for recipe_summary in recipe_results:
                # Get full recipe details
                recipe_details = spoonacular_client.get_recipe_details(recipe_summary["id"])
                
                # Parse ingredients
                recipe_ingredients = self._parse_recipe_ingredients_from_api(recipe_details)
                
                # Calculate score
                score = self.pantry_analyzer.calculate_match_score(
                    recipe_ingredients=recipe_ingredients,
                    expiring_items=expiring_items,
                    day_num=day_num
                )
                
                scored_recipes.append((recipe_details, score))
            
            # Sort by score descending
            scored_recipes.sort(key=lambda x: x[1], reverse=True)
            
            # Get best recipe
            best_recipe_data, best_score = scored_recipes[0]
            
            # Check if score meets minimum threshold
            if best_score < settings.MIN_INGREDIENT_MATCH_PERCENTAGE:
                logger.info(f"Best recipe score ({best_score:.1f}) below threshold")
                # Still return it, but calling function can decide what to do
            
            # Convert to Recipe model
            recipe = self._convert_to_recipe_model(best_recipe_data)
            
            return recipe, best_score
            
        except Exception as e:
            logger.error(f"Error finding recipe: {str(e)}")
            return None, 0.0
    
    def _parse_recipe_ingredients(self, recipe: Recipe) -> List[RecipeIngredient]:
        """Parse recipe ingredients into standardized format."""
        return recipe.ingredients
    
    def _parse_recipe_ingredients_from_api(
        self,
        recipe_data: Dict[str, Any]
    ) -> List[RecipeIngredient]:
        """
        Parse recipe ingredients from Spoonacular API response.
        
        Args:
            recipe_data: Raw recipe data from API
            
        Returns:
            List of RecipeIngredient objects
        """
        ingredients = []
        
        for ing in recipe_data.get("extendedIngredients", []):
            ingredients.append(RecipeIngredient(
                name=ing.get("name", ing.get("nameClean", "unknown")),
                quantity=ing.get("amount", 0),
                unit=ing.get("unit", ""),
                from_pantry=False
            ))
        
        return ingredients
    
    def _convert_to_recipe_model(self, recipe_data: Dict[str, Any]) -> Recipe:
        """
        Convert Spoonacular API response to Recipe model.
        
        Args:
            recipe_data: Raw recipe data from API
            
        Returns:
            Recipe model instance
        """
        # Parse ingredients
        ingredients = self._parse_recipe_ingredients_from_api(recipe_data)
        
        # Parse instructions
        instructions = []
        if "analyzedInstructions" in recipe_data and recipe_data["analyzedInstructions"]:
            for instruction_set in recipe_data["analyzedInstructions"]:
                for step in instruction_set.get("steps", []):
                    instructions.append(step.get("step", ""))
        elif "instructions" in recipe_data:
            # Fallback to plain text instructions
            instructions = [recipe_data["instructions"]]
        
        return Recipe(
            id=recipe_data.get("id", 0),
            name=recipe_data.get("title", "Unknown Recipe"),
            image=recipe_data.get("image"),
            ready_in_minutes=recipe_data.get("readyInMinutes", 30),
            servings=recipe_data.get("servings", self.config.servings),
            ingredients=ingredients,
            instructions=instructions,
            source_url=recipe_data.get("sourceUrl")
        )
    
    async def _handle_empty_pantry(
        self,
        meal_type: MealTypeEnum
    ) -> Tuple[Meal, List[ShoppingListItem]]:
        """Handle case when pantry is empty."""
        # Return a simple default recipe with shopping list
        default_recipe = Recipe(
            id=0,
            name=f"Simple {meal_type.value.title()}",
            ready_in_minutes=15,
            servings=self.config.servings,
            ingredients=[],
            instructions=["Please restock your pantry to get recipe suggestions."]
        )
        
        shopping_list = [
            ShoppingListItem(
                name="Basic pantry items needed",
                quantity=1,
                unit="set",
                needed_for=[]
            )
        ]
        
        meal = Meal(
            meal_type=meal_type,
            recipe=default_recipe,
            ingredients_used=[],
            shopping_list=shopping_list,
            note="Pantry is empty. Please add items to get personalized meal suggestions.",
            match_score=0.0
        )
        
        return meal, shopping_list
    
    async def _handle_no_recipe_found(
        self,
        meal_type: MealTypeEnum,
        expiring_items: Dict[str, int]
    ) -> Tuple[Meal, List[ShoppingListItem]]:
        """Handle case when no suitable recipe is found."""
        # Suggest using expiring items
        if expiring_items:
            expiring_list = list(expiring_items.keys())[:3]
            note = f"Consider using expiring items: {', '.join(expiring_list)}"
        else:
            note = "No matching recipes found. Consider shopping for fresh ingredients."
        
        default_recipe = Recipe(
            id=0,
            name=f"Custom {meal_type.value.title()}",
            ready_in_minutes=30,
            servings=self.config.servings,
            ingredients=[],
            instructions=["Create your own recipe with available ingredients."]
        )
        
        meal = Meal(
            meal_type=meal_type,
            recipe=default_recipe,
            ingredients_used=[],
            shopping_list=[],
            note=note,
            match_score=0.0
        )
        
        return meal, []
    
    def _aggregate_shopping_list(
        self,
        shopping_items: List[ShoppingListItem]
    ) -> List[ShoppingListItem]:
        """
        Aggregate shopping list items by combining duplicates.
        
        Args:
            shopping_items: List of all shopping items
            
        Returns:
            Aggregated shopping list
        """
        aggregated: Dict[str, ShoppingListItem] = {}
        
        for item in shopping_items:
            key = f"{item.name.lower()}_{item.unit.lower()}"
            
            if key in aggregated:
                # Combine quantities
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