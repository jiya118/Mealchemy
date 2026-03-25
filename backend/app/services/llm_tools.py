"""
LLM tools for agentic meal planning.
Provides tools that LLM can call to search recipes, update pantry, etc.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from app.crud.recipe import RecipeCRUD
from app.schema.recipe import CachedRecipeResponse
from app.services.spoonacular_client import spoonacular_client

logger = logging.getLogger(__name__)


class MealPlanningTools:
    """Tools that LLM can use for intelligent meal planning."""
    
    def __init__(
        self,
        recipe_crud: RecipeCRUD,
        initial_pantry: Dict[str, Dict[str, Any]]
    ):
        """
        Initialize meal planning tools.
        
        Args:
            recipe_crud: Recipe cache CRUD
            initial_pantry: Virtual pantry state {item_name: {quantity, unit, expires}}
        """
        self.recipe_crud = recipe_crud
        self.virtual_pantry = initial_pantry.copy()
        self.spoonacular_calls_made = 0
        self.spoonacular_call_limit = 2  # Max Spoonacular calls per session
        
        logger.info(f"Initialized tools with {len(self.virtual_pantry)} pantry items")
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions for LLM.
        
        Returns:
            List of tool schemas in OpenAI function format
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_cached_recipes",
                    "description": "Search recipe cache for recipes using given main ingredients. Use this FIRST before calling Spoonacular. Returns cached recipes that match the ingredients.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ingredients": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Main ingredients to search for (e.g., ['chicken', 'tomatoes', 'rice']). Focus on proteins and vegetables, ignore spices/oils."
                            },
                            "diet_type": {
                                "type": "string",
                                "enum": ["standard", "vegetarian", "vegan"],
                                "description": "Optional diet filter"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum recipes to return (default 10)"
                            }
                        },
                        "required": ["ingredients"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_spoonacular",
                    "description": "Search Spoonacular API for new recipes. RATE LIMITED: You can call this maximum 2 times per session. Only use when cache doesn't have good options. This will automatically cache the results.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ingredients": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Main ingredients (proteins, vegetables). Max 5 ingredients for best results."
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of recipes to fetch (max 10)"
                            },
                            "diet_type": {
                                "type": "string",
                                "enum": ["standard", "vegetarian", "vegan"],
                                "description": "Diet filter"
                            }
                        },
                        "required": ["ingredients"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_recipe_details",
                    "description": "Get full details for a specific recipe by its ID. Use this to see complete ingredients list and instructions before selecting a recipe.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "recipe_id": {
                                "type": "string",
                                "description": "Recipe identifier from search results (e.g., 'spoon_123456')"
                            }
                        },
                        "required": ["recipe_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_virtual_pantry",
                    "description": "Deduct ingredients from virtual pantry after selecting a recipe. Call this after choosing each meal to track what's remaining for future days.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "used_ingredients": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "quantity": {"type": "number"},
                                        "unit": {"type": "string"}
                                    },
                                    "required": ["name", "quantity", "unit"]
                                },
                                "description": "List of ingredients used in the meal"
                            }
                        },
                        "required": ["used_ingredients"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_current_pantry",
                    "description": "Get current state of virtual pantry with remaining quantities. Use this to see what's available for planning future days.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]
    
    async def search_cached_recipes(
        self,
        ingredients: List[str],
        diet_type: Optional[str] = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Search recipe cache.
        
        Args:
            ingredients: Main ingredients to search for
            diet_type: Diet filter
            max_results: Max recipes to return
            
        Returns:
            Search results with recipes
        """
        logger.info(f"Cache search: {ingredients}")
        
        # Normalize ingredients
        normalized = [ing.lower().strip() for ing in ingredients]
        
        # Search cache
        cached_recipes = await self.recipe_crud.find_by_ingredients(
            ingredient_hashes=normalized,
            diet_type=diet_type,
            limit=max_results
        )
        
        # Convert to lightweight format
        results = []
        for recipe in cached_recipes:
            results.append({
                "id": recipe.recipe_id,
                "name": recipe.name,
                "ingredients_needed": [
                    {"name": ing.name, "quantity": ing.quantity, "unit": ing.unit}
                    for ing in recipe.ingredients_summary
                ],
                "prep_time": recipe.ready_in_minutes,
                "servings": recipe.servings,
                "diet_types": recipe.diet_types,
                "meal_types": recipe.meal_types
            })
        
        logger.info(f"Found {len(results)} cached recipes")
        
        return {
            "found": len(results),
            "recipes": results,
            "source": "cache"
        }
    
    async def search_spoonacular(
        self,
        ingredients: List[str],
        count: int = 5,
        diet_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search Spoonacular API (rate limited).
        
        Args:
            ingredients: Main ingredients
            count: Number to fetch
            diet_type: Diet filter
            
        Returns:
            Search results with new recipes
        """
        # Check rate limit
        if self.spoonacular_calls_made >= self.spoonacular_call_limit:
            logger.warning("Spoonacular rate limit reached")
            return {
                "error": f"Rate limit reached. You've already made {self.spoonacular_calls_made} Spoonacular calls. Use cached recipes instead.",
                "found": 0,
                "recipes": []
            }
        
        logger.info(f"Spoonacular search: {ingredients} (call {self.spoonacular_calls_made + 1}/{self.spoonacular_call_limit})")
        
        try:
            # Limit ingredients to 5 for best results
            search_ingredients = ingredients[:5]
            ingredients_str = ",".join(search_ingredients)
            
            # Map diet type
            spoon_diet = None if diet_type == "standard" else diet_type
            
            # Search Spoonacular
            recipe_summaries = spoonacular_client.search_recipes_by_ingredients(
                ingredients=ingredients_str,
                number=min(count, 10),
                ranking=1,
                diet=spoon_diet
            )
            
            self.spoonacular_calls_made += 1
            
            if not recipe_summaries:
                return {
                    "found": 0,
                    "recipes": [],
                    "source": "spoonacular",
                    "calls_remaining": self.spoonacular_call_limit - self.spoonacular_calls_made
                }
            
            # Fetch details and cache
            results = []
            for summary in recipe_summaries[:count]:
                # Get full details
                full_recipe = spoonacular_client.get_recipe_details(summary['id'])
                
                # Cache it
                from app.services.recipe_cache_manager import RecipeCacheManager
                cache_manager = RecipeCacheManager(self.recipe_crud)
                cached = await cache_manager.cache_spoonacular_recipe(full_recipe, diet_type)
                saved = await self.recipe_crud.create(cached)
                
                # Add to results
                results.append({
                    "id": saved.recipe_id,
                    "name": saved.name,
                    "ingredients_needed": [
                        {"name": ing.name, "quantity": ing.quantity, "unit": ing.unit}
                        for ing in saved.ingredients_summary
                    ],
                    "prep_time": saved.ready_in_minutes,
                    "servings": saved.servings,
                    "diet_types": saved.diet_types,
                    "meal_types": saved.meal_types
                })
            
            logger.info(f"Fetched and cached {len(results)} recipes from Spoonacular")
            
            return {
                "found": len(results),
                "recipes": results,
                "source": "spoonacular",
                "calls_remaining": self.spoonacular_call_limit - self.spoonacular_calls_made
            }
            
        except Exception as e:
            logger.error(f"Spoonacular search failed: {str(e)}")
            return {
                "error": str(e),
                "found": 0,
                "recipes": [],
                "calls_remaining": self.spoonacular_call_limit - self.spoonacular_calls_made
            }
    
    async def get_recipe_details(self, recipe_id: str) -> Dict[str, Any]:
        """
        Get full recipe details.
        
        Args:
            recipe_id: Recipe identifier
            
        Returns:
            Full recipe details
        """
        logger.info(f"Getting details for: {recipe_id}")
        
        # Get from cache
        recipe = await self.recipe_crud.get_by_recipe_id(recipe_id)
        
        if not recipe:
            return {
                "error": f"Recipe {recipe_id} not found in cache",
                "found": False
            }
        
        # Validate recipe is actually a meal (not condiment/beverage/side)
        name_lower = recipe.name.lower()
        invalid_keywords = [
            'chutney', 'sauce', 'dip', 'condiment', 'spread',
            'smoothie', 'juice', 'drink', 'beverage', 'cocktail', 'latte',
            'salad', 'bread', 'biscuit', 'cookie', 'muffin'
        ]
        
        # Check if recipe name contains any invalid keywords
        is_valid_meal = True
        for keyword in invalid_keywords:
            if keyword in name_lower:
                is_valid_meal = False
                logger.warning(f"Recipe '{recipe.name}' rejected - contains '{keyword}' (not a proper meal)")
                break
        
        # Also check if recipe has minimal ingredients (condiments usually have <5)
        if len(recipe.ingredients_summary) < 5:
            is_valid_meal = False
            logger.warning(f"Recipe '{recipe.name}' rejected - only {len(recipe.ingredients_summary)} ingredients")
        
        if not is_valid_meal:
            return {
                "error": f"Recipe '{recipe.name}' is not a proper meal (appears to be a condiment/beverage/side)",
                "found": False,
                "suggestion": "Try searching for a different recipe with main protein and vegetables"
            }
        
        # Extract instructions from full_recipe
        instructions = []
        if "analyzedInstructions" in recipe.full_recipe:
            for instruction_set in recipe.full_recipe["analyzedInstructions"]:
                for step in instruction_set.get("steps", []):
                    instructions.append(step.get("step", ""))
        elif "instructions" in recipe.full_recipe:
            instructions = [recipe.full_recipe["instructions"]]
        
        return {
            "found": True,
            "id": recipe.recipe_id,
            "name": recipe.name,
            "ingredients": [
                {"name": ing.name, "quantity": ing.quantity, "unit": ing.unit}
                for ing in recipe.ingredients_summary
            ],
            "instructions": instructions,
            "prep_time": recipe.ready_in_minutes,
            "servings": recipe.servings,
            "diet_types": recipe.diet_types
        }
    
    def update_virtual_pantry(
        self,
        used_ingredients: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Update virtual pantry by deducting used ingredients.
        
        Args:
            used_ingredients: List of {name, quantity, unit}
            
        Returns:
            Updated pantry state
        """
        logger.info(f"Updating pantry: {len(used_ingredients)} ingredients used")
        
        depleted_items = []
        
        for ing in used_ingredients:
            name_lower = ing["name"].lower().strip()
            
            # Find in pantry (exact or partial match)
            pantry_key = None
            for key in self.virtual_pantry.keys():
                if name_lower == key.lower() or name_lower in key.lower() or key.lower() in name_lower:
                    pantry_key = key
                    break
            
            if pantry_key:
                # Deduct quantity
                current_qty = self.virtual_pantry[pantry_key]["quantity"]
                used_qty = ing["quantity"]
                new_qty = max(0, current_qty - used_qty)
                
                self.virtual_pantry[pantry_key]["quantity"] = new_qty
                
                logger.debug(f"Deducted {used_qty} {ing['unit']} of {pantry_key} (remaining: {new_qty})")
                
                if new_qty == 0:
                    depleted_items.append(pantry_key)
        
        # Get current state
        remaining_items = {
            name: details
            for name, details in self.virtual_pantry.items()
            if details["quantity"] > 0
        }
        
        return {
            "updated": True,
            "depleted_items": depleted_items,
            "remaining_count": len(remaining_items),
            "remaining_items": remaining_items
        }
    
    def get_current_pantry(self) -> Dict[str, Any]:
        """
        Get current pantry state.
        
        Returns:
            Current pantry inventory
        """
        remaining = {
            name: details
            for name, details in self.virtual_pantry.items()
            if details["quantity"] > 0
        }
        
        return {
            "total_items": len(remaining),
            "items": remaining
        }
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool by name.
        
        Args:
            tool_name: Name of tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        if tool_name == "search_cached_recipes":
            return await self.search_cached_recipes(**arguments)
        
        elif tool_name == "search_spoonacular":
            return await self.search_spoonacular(**arguments)
        
        elif tool_name == "get_recipe_details":
            return await self.get_recipe_details(**arguments)
        
        elif tool_name == "update_virtual_pantry":
            return self.update_virtual_pantry(**arguments)
        
        elif tool_name == "get_current_pantry":
            return self.get_current_pantry()
        
        else:
            return {"error": f"Unknown tool: {tool_name}"}