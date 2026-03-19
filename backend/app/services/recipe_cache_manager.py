"""
Recipe cache manager - handles recipe caching and matching.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import logging

from app.schema.recipe import (
    CachedRecipe,
    CachedRecipeResponse,
    SimpleIngredient,
    RecipeSource
)
from app.crud.recipe import RecipeCRUD
from app.services.spoonacular_client import spoonacular_client

logger = logging.getLogger(__name__)


class RecipeCacheManager:
    """Manages recipe cache with intelligent matching."""
    
    # Common pantry staples that shouldn't be used in recipe search
    PANTRY_STAPLES = {
        # Spices & Seasonings
        'salt', 'pepper', 'black pepper', 'white pepper', 'red pepper',
        'black pepper powder', 'white pepper powder',
        'chili powder', 'red chili powder', 'green chili powder',
        'turmeric', 'turmeric powder', 'haldi',
        'cumin', 'cumin seeds', 'cumin powder', 'jeera',
        'coriander', 'coriander powder', 'coriander seeds', 'dhaniya',
        'garam masala', 'curry powder', 'masala',
        'paprika', 'cayenne', 'oregano', 'basil', 'thyme', 'rosemary',
        'cinnamon', 'cardamom', 'cloves', 'nutmeg', 'bay leaves',
        'mustard seeds', 'fenugreek', 'fennel seeds',
        'asafoetida', 'hing', 'ajwain', 'carom seeds',
        
        # Oils & Fats
        'oil', 'olive oil', 'vegetable oil', 'canola oil', 'sunflower oil',
        'mustard oil', 'sesame oil', 'coconut oil',
        'ghee', 'butter', 'margarine',
        
        # Condiments & Sauces
        'vinegar', 'soy sauce', 'fish sauce', 'worcestershire sauce',
        'ketchup', 'mustard', 'mayonnaise',
        
        # Baking & Sweeteners
        'sugar', 'brown sugar', 'white sugar', 'powdered sugar',
        'honey', 'maple syrup', 'molasses',
        'flour', 'all purpose flour', 'wheat flour', 'atta', 'maida',
        'whole wheat flour', 'bread flour', 'cake flour',
        'baking powder', 'baking soda', 'yeast',
        'cornstarch', 'corn flour',
        
        # Beverages
        'tea', 'chai leaves', 'coffee', 'coffee powder',
        'water',
        
        # Processed/Packaged
        'bread', 'biscuits', 'cookies', 'crackers',
        'noodles', 'maggi', 'pasta',
    }
    
    def __init__(self, recipe_crud: RecipeCRUD):
        self.recipe_crud = recipe_crud
    
    @staticmethod
    def normalize_ingredient(ingredient: str) -> str:
        """
        Normalize ingredient name for hashing.
        
        Args:
            ingredient: Raw ingredient name
            
        Returns:
            Normalized name
        """
        # Convert to lowercase, remove extra spaces
        normalized = ingredient.lower().strip()
        
        # Remove common words that don't affect matching
        remove_words = ["fresh", "dried", "chopped", "minced", "sliced", "diced"]
        for word in remove_words:
            normalized = normalized.replace(word, "").strip()
        
        # Remove extra spaces
        normalized = " ".join(normalized.split())
        
        return normalized
    
    @staticmethod
    def is_pantry_staple(ingredient: str) -> bool:
        """
        Check if ingredient is a common pantry staple.
        
        Args:
            ingredient: Ingredient name
            
        Returns:
            True if it's a staple, False if it's a main ingredient
        """
        normalized = ingredient.lower().strip()
        
        # Check exact match
        if normalized in RecipeCacheManager.PANTRY_STAPLES:
            return True
        
        # Check if any staple is contained in the ingredient name
        for staple in RecipeCacheManager.PANTRY_STAPLES:
            if staple in normalized:
                return True
        
        return False
    
    @staticmethod
    def filter_main_ingredients(ingredients: List[str], max_count: int = 10) -> List[str]:
        """
        Filter out pantry staples and return only main ingredients.
        
        Args:
            ingredients: All pantry ingredients
            max_count: Maximum main ingredients to return
            
        Returns:
            List of main ingredients only
        """
        main_ingredients = [
            ing for ing in ingredients
            if not RecipeCacheManager.is_pantry_staple(ing)
        ]
        
        # Return top N ingredients
        return main_ingredients[:max_count]
    
    @staticmethod
    def create_ingredients_hash(ingredients: List[str]) -> str:
        """
        Create a hash from ingredient list.
        
        Args:
            ingredients: List of ingredient names
            
        Returns:
            Hash string (e.g., "gar_len_oni_tom")
        """
        # Normalize all ingredients
        normalized = [
            RecipeCacheManager.normalize_ingredient(ing)
            for ing in ingredients
        ]
        
        # Take first 3-4 letters of each, sort alphabetically
        prefixes = sorted([ing[:3] for ing in normalized if ing])
        
        return "_".join(prefixes)
    
    async def find_cached_recipes(
        self,
        pantry_ingredients: List[str],
        diet_type: Optional[str] = None,
        meal_type: Optional[str] = None,
        min_recipes: int = 15
    ) -> List[CachedRecipeResponse]:
        """
        Find recipes in cache matching pantry ingredients.
        
        Args:
            pantry_ingredients: Available ingredients
            diet_type: Filter by diet
            meal_type: Filter by meal type
            min_recipes: Minimum recipes to return
            
        Returns:
            List of matching cached recipes
        """
        # Normalize pantry ingredients
        normalized_ingredients = [
            self.normalize_ingredient(ing) for ing in pantry_ingredients
        ]
        
        # Find matching recipes
        cached = await self.recipe_crud.find_by_ingredients(
            ingredient_hashes=normalized_ingredients,
            diet_type=diet_type,
            meal_type=meal_type,
            limit=min_recipes * 2  # Get extra for filtering
        )
        
        logger.info(f"Found {len(cached)} cached recipes matching pantry")
        
        return cached[:min_recipes]
    
    async def cache_spoonacular_recipe(
        self,
        spoon_recipe: Dict[str, Any],
        diet_type: Optional[str] = None
    ) -> CachedRecipe:
        """
        Convert Spoonacular recipe to cached format and save.
        
        Args:
            spoon_recipe: Full Spoonacular recipe response
            diet_type: Diet type to tag recipe with
            
        Returns:
            Cached recipe
        """
        # Extract ingredients
        ingredients_simple = []
        ingredients_summary = []
        
        for ing in spoon_recipe.get("extendedIngredients", []):
            name = self.normalize_ingredient(
                ing.get("name", ing.get("nameClean", ""))
            )
            if name:
                ingredients_simple.append(name)
                ingredients_summary.append(SimpleIngredient(
                    name=name,
                    quantity=ing.get("amount", 0),
                    unit=ing.get("unit", "")
                ))
        
        # Create hash
        ingredients_hash = self.create_ingredients_hash(ingredients_simple)
        
        # Determine diet types
        diet_types = []
        if spoon_recipe.get("vegetarian"):
            diet_types.append("vegetarian")
        if spoon_recipe.get("vegan"):
            diet_types.append("vegan")
        if diet_type and diet_type not in diet_types:
            diet_types.append(diet_type)
        if not diet_types:
            diet_types.append("standard")
        
        # Determine meal types
        dish_types = spoon_recipe.get("dishTypes", [])
        meal_types = []
        for dish_type in dish_types:
            if dish_type in ["breakfast", "lunch", "dinner"]:
                meal_types.append(dish_type)
        if not meal_types:
            meal_types = ["lunch", "dinner"]  # Default
        
        # Create cached recipe
        cached_recipe = CachedRecipe(
            recipe_id=f"spoon_{spoon_recipe['id']}",
            name=spoon_recipe.get("title", "Unknown Recipe"),
            source=RecipeSource.SPOONACULAR,
            ingredients_simple=ingredients_simple,
            ingredients_hash=ingredients_hash,
            ingredients_summary=ingredients_summary,
            full_recipe=spoon_recipe,
            diet_types=diet_types,
            meal_types=meal_types,
            cuisine=spoon_recipe.get("cuisines", [None])[0] if spoon_recipe.get("cuisines") else None,
            ready_in_minutes=spoon_recipe.get("readyInMinutes", 30),
            servings=spoon_recipe.get("servings", 2),
            times_used=0,
            last_used_date=None,
            user_rating=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        return cached_recipe
    
    async def fetch_and_cache_new_recipes(
        self,
        pantry_ingredients: List[str],
        diet_type: Optional[str] = None,
        meal_type: Optional[str] = None,
        count: int = 10
    ) -> List[CachedRecipeResponse]:
        """
        Fetch new recipes from Spoonacular and cache them.
        
        Args:
            pantry_ingredients: Available ingredients
            diet_type: Diet filter
            meal_type: Meal type filter
            count: Number of recipes to fetch
            
        Returns:
            List of newly cached recipes
        """
        # Filter to main ingredients only (remove spices, oils, etc.)
        main_ingredients = self.filter_main_ingredients(pantry_ingredients, max_count=10)
        
        if not main_ingredients:
            logger.warning("No main ingredients found after filtering staples")
            # If everything is filtered out, use top 5 original ingredients
            main_ingredients = pantry_ingredients[:5]
        
        logger.info(f"Searching with main ingredients: {', '.join(main_ingredients)}")
        
        # Prepare ingredients string for Spoonacular
        ingredients_str = ",".join(main_ingredients)
        
        # Map diet type
        spoon_diet = None if diet_type == "standard" else diet_type
        if diet_type == "eggetarian":
            spoon_diet = "vegetarian"
        
        try:
            # Search Spoonacular
            logger.info(f"Fetching {count} new recipes from Spoonacular")
            recipe_summaries = spoonacular_client.search_recipes_by_ingredients(
                ingredients=ingredients_str,
                number=count,
                ranking=1,
                diet=spoon_diet,
                meal_type=meal_type
            )
            
            if not recipe_summaries:
                logger.warning("No recipes found from Spoonacular")
                return []
            
            # Fetch full details and cache
            cached_recipes = []
            for summary in recipe_summaries:
                # Check if already cached
                existing = await self.recipe_crud.get_by_recipe_id(f"spoon_{summary['id']}")
                if existing:
                    logger.debug(f"Recipe {summary['id']} already cached")
                    cached_recipes.append(existing)
                    continue
                
                # Fetch full details
                full_recipe = spoonacular_client.get_recipe_details(summary['id'])
                
                # Convert to cached format
                cached_recipe = await self.cache_spoonacular_recipe(full_recipe, diet_type)
                
                # Save to database
                saved = await self.recipe_crud.create(cached_recipe)
                cached_recipes.append(saved)
                
                logger.info(f"Cached new recipe: {cached_recipe.name}")
            
            return cached_recipes
            
        except Exception as e:
            logger.error(f"Failed to fetch/cache recipes: {str(e)}")
            return []
    
    async def get_recipe_candidates(
        self,
        pantry_ingredients: List[str],
        diet_type: Optional[str] = None,
        meal_type: Optional[str] = None,
        target_count: int = 20
    ) -> List[CachedRecipeResponse]:
        """
        Get recipe candidates, using cache first then Spoonacular if needed.
        
        Args:
            pantry_ingredients: Available ingredients
            diet_type: Diet filter
            meal_type: Meal type filter
            target_count: Target number of candidates
            
        Returns:
            List of recipe candidates
        """
        # Try cache first
        cached = await self.find_cached_recipes(
            pantry_ingredients=pantry_ingredients,
            diet_type=diet_type,
            meal_type=meal_type,
            min_recipes=target_count
        )
        
        # If cache has enough, return
        if len(cached) >= target_count:
            logger.info(f"Using {len(cached)} recipes from cache (no API call needed)")
            return cached[:target_count]
        
        # Need more recipes - fetch from Spoonacular
        logger.info(f"Cache has only {len(cached)} recipes, fetching {target_count - len(cached)} more")
        new_recipes = await self.fetch_and_cache_new_recipes(
            pantry_ingredients=pantry_ingredients,
            diet_type=diet_type,
            meal_type=meal_type,
            count=target_count - len(cached)
        )
        
        # Combine cached + new
        all_recipes = cached + new_recipes
        
        return all_recipes[:target_count]