"""
Spoonacular API client with caching.
"""
import httpx
from functools import lru_cache
from typing import List, Dict, Any, Optional
import logging

from app.core.settings import settings

logger = logging.getLogger(__name__)


class SpoonacularClient:
    """Client for Spoonacular Recipe API with built-in caching."""
    
    def __init__(self):
        self.base_url = settings.SPOONACULAR_BASE_URL
        self.api_key = settings.SPOONACULAR_API_KEY
        self.timeout = 30.0
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to Spoonacular API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response
        """
        params["apiKey"] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Spoonacular API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request failed: {str(e)}")
            raise
    
    @lru_cache(maxsize=settings.RECIPE_CACHE_SIZE)
    def search_recipes_by_ingredients(
        self,
        ingredients: str,
        number: int = 10,
        ranking: int = 1,
        ignore_pantry: bool = False,
        diet: Optional[str] = None,
        intolerances: Optional[str] = None,
        meal_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search recipes by available ingredients (CACHED).
        
        Args:
            ingredients: Comma-separated list of ingredients
            number: Number of recipes to return
            ranking: 1 = maximize used ingredients, 2 = minimize missing
            ignore_pantry: Whether to ignore pantry items
            diet: Diet type (vegetarian, vegan, etc.)
            intolerances: Comma-separated intolerances
            meal_type: breakfast, lunch, dinner, snack, dessert
            
        Returns:
            List of recipe summaries
        """
        params = {
            "ingredients": ingredients,
            "number": number,
            "ranking": ranking,
            "ignorePantry": ignore_pantry
        }
        
        if diet:
            params["diet"] = diet
        if intolerances:
            params["intolerances"] = intolerances
        if meal_type:
            params["type"] = meal_type
        
        logger.info(f"Searching recipes with ingredients: {ingredients[:50]}...")
        result = self._make_request("recipes/findByIngredients", params)
        logger.info(f"Found {len(result)} recipes")
        
        return result
    
    @lru_cache(maxsize=settings.RECIPE_CACHE_SIZE)
    def get_recipe_details(self, recipe_id: int) -> Dict[str, Any]:
        """
        Get detailed recipe information (CACHED).
        
        Args:
            recipe_id: Spoonacular recipe ID
            
        Returns:
            Complete recipe details
        """
        logger.info(f"Fetching details for recipe {recipe_id}")
        
        params = {
            "includeNutrition": False
        }
        
        result = self._make_request(f"recipes/{recipe_id}/information", params)
        return result
    
    def parse_ingredients(self, ingredient_list: str, servings: int = 1) -> List[Dict[str, Any]]:
        """
        Parse ingredient list into structured format.
        
        Args:
            ingredient_list: Newline-separated ingredient list
            servings: Number of servings
            
        Returns:
            Parsed ingredients with amounts and units
        """
        params = {
            "ingredientList": ingredient_list,
            "servings": servings
        }
        
        result = self._make_request("recipes/parseIngredients", params)
        return result
    
    def convert_amounts(
        self,
        ingredient_name: str,
        source_amount: float,
        source_unit: str,
        target_unit: str
    ) -> Dict[str, Any]:
        """
        Convert ingredient amounts between units.
        
        Args:
            ingredient_name: Name of ingredient
            source_amount: Amount to convert
            source_unit: Current unit
            target_unit: Desired unit
            
        Returns:
            Conversion result
        """
        params = {
            "ingredientName": ingredient_name,
            "sourceAmount": source_amount,
            "sourceUnit": source_unit,
            "targetUnit": target_unit
        }
        
        result = self._make_request("recipes/convert", params)
        return result
    
    def clear_cache(self):
        """Clear all cached API responses."""
        self.search_recipes_by_ingredients.cache_clear()
        self.get_recipe_details.cache_clear()
        logger.info("Spoonacular API cache cleared")


# Global client instance
spoonacular_client = SpoonacularClient()