"""
Agentic meal planner - LLM-driven meal planning with tool calling.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

from app.schema.pantryItem import PantryItemResponse
from app.schema.meal_plan import MealPlanConfig
from app.services.llm_tools import MealPlanningTools
from app.services.agentic_llm_client import agentic_llm_client
from app.crud.recipe import RecipeCRUD

logger = logging.getLogger(__name__)


class AgenticMealPlanner:
    """LLM-driven meal planner with tool calling."""
    
    DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    
    def __init__(self, pantry_items: List[PantryItemResponse], recipe_crud: RecipeCRUD):
        """
        Initialize agentic meal planner.
        
        Args:
            pantry_items: Current pantry inventory
            recipe_crud: Recipe CRUD instance
        """
        self.pantry_items = pantry_items
        self.recipe_crud = recipe_crud
        
        # Convert pantry to virtual format
        self.virtual_pantry = self._create_virtual_pantry(pantry_items)
    
    def _create_virtual_pantry(
        self,
        pantry_items: List[PantryItemResponse]
    ) -> Dict[str, Dict[str, Any]]:
        """Create virtual pantry dictionary."""
        virtual = {}
        
        for item in pantry_items:
            if item.quantity and item.quantity > 0:
                expiry_str = None
                if item.expiry_date:
                    if isinstance(item.expiry_date, datetime):
                        expiry_str = item.expiry_date.strftime("%Y-%m-%d")
                    else:
                        expiry_str = str(item.expiry_date)
                
                virtual[item.name] = {
                    "id": item.id,
                    "quantity": item.quantity,
                    "unit": item.unit if item.unit else "",
                    "category": item.category if item.category else "other",
                    "expires": expiry_str
                }
        
        return virtual
    
    def _build_system_prompt(self, config: MealPlanConfig) -> str:
        """Build system prompt for LLM."""
        
        meal_type = "dinner" if config.meals_per_day == 1 else "lunch and dinner"
        
        prompt = f"""You are a meal planner. You MUST only suggest meals that can be made from the ingredients currently in the user's pantry. Plan {config.days} days of {meal_type} for {config.servings} person(s).

DIET: {config.diet_type}

STRICT RULES:
1. Always call get_current_pantry FIRST before planning anything.
2. Search for recipes using the ACTUAL pantry ingredients — not random ingredients.
3. A recipe should only be selected if at least 70% of its required ingredients are available in the pantry.
4. If a recipe needs 1-2 missing ingredients, those MUST be added to shopping_needed for that meal.
5. Do NOT suggest meals that require ingredients not in the pantry unless absolutely necessary.
6. Prioritize using ingredients that are expiring soonest (earliest expiry_date).
7. After each meal is planned, call update_virtual_pantry to deduct used ingredients so the next day's meal is planned based on what actually remains.
8. Weekdays (Mon-Fri): Quick meals (≤30 min). Weekends: Can be elaborate (≤60 min).
9. Don't repeat main ingredients within 3 days.
10. Search cache first, call Spoonacular only if needed (max 2 calls).

WORKFLOW PER DAY:
1. Call get_current_pantry()
2. Pick 2-3 main ingredients FROM THE PANTRY (proteins/vegetables, prioritize expiring items)
3. Call search_cached_recipes(["chicken", "tomatoes"]) — use REAL pantry items here
4. If cache has 3+ options: Pick the best one
5. If cache <3: Call search_spoonacular(["chicken"], count=5) — max 2 Spoonacular calls total
6. Call get_recipe_details(recipe_id) — this will reject non-meals (condiments/drinks/sides)
7. If rejected, search for a different recipe
8. Once you have a valid meal, call update_virtual_pantry([{{"name": "chicken", "quantity": 200, "unit": "g"}}])
9. REPEAT for ALL {config.days} days

CRITICAL: Plan meals for ALL {config.days} days (monday through {self.DAYS_OF_WEEK[config.days-1]}). Don't stop early!

IMPORTANT:
- Focus on MAIN ingredients (proteins, vegetables)
- Ignore spices/oils/flour/sugar when searching
- Max 2 Spoonacular calls total
- The final output must include a total_shopping_list of all missing ingredients across all days

OUTPUT (JSON only):
{{
  "meals": [
    {{
      "day": "monday",
      "recipe_id": "spoon_123",
      "recipe_name": "Chicken Stir Fry",
      "reasoning": "Quick, uses expiring chicken",
      "prep_time": 20,
      "ingredients_used": [{{"name": "chicken", "quantity": 200, "unit": "g"}}],
      "shopping_needed": []
    }}
  ],
  "total_shopping_list": [{{"name": "soy sauce", "quantity": 1, "unit": "tbsp"}}],
  "summary": {{
    "total_spoonacular_calls": 1
  }}
}}

Respond with ONLY JSON, no markdown."""

        return prompt
    
    def _build_user_message(self) -> str:
        """Build initial user message with pantry data."""
        
        # Prepare pantry summary - CONDENSED to reduce tokens
        import json
        pantry_items = []
        expiring_soon = []
        
        # Only include items with quantity > 0 and skip very common staples
        skip_items = {'water', 'salt', 'pepper', 'oil'}
        
        for name, details in self.virtual_pantry.items():
            # Skip staples to reduce tokens
            if name.lower() in skip_items:
                continue
                
            pantry_items.append({
                "name": name,
                "qty": details["quantity"],
                "unit": details["unit"],
                "exp": details["expires"]  # Shortened key
            })
            
            # Flag items expiring soon
            if details["expires"]:
                try:
                    expiry_date = datetime.strptime(details["expires"], "%Y-%m-%d")
                    days_until_expiry = (expiry_date - datetime.utcnow()).days
                    if 0 <= days_until_expiry <= 7:
                        expiring_soon.append(f"{name} ({days_until_expiry}d)")
                except:
                    pass
        
        # Limit to 30 items to reduce token usage
        pantry_items = pantry_items[:30]
        
        message = f"""PANTRY ({len(pantry_items)} items):
{json.dumps(pantry_items, indent=1)}

EXPIRING SOON: {', '.join(expiring_soon) if expiring_soon else 'None'}

Plan meals using tools. Search cache first, use Spoonacular only if needed."""

        return message
    
    async def plan_meals(
        self,
        config: MealPlanConfig
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Plan meals using LLM with tools.
        
        Args:
            config: Meal plan configuration
            
        Returns:
            Tuple of (meal_plan_dict, error_message)
        """
        logger.info(f"Starting agentic meal planning for {config.days} days")
        
        # Initialize tools
        tools_instance = MealPlanningTools(
            recipe_crud=self.recipe_crud,
            initial_pantry=self.virtual_pantry
        )
        
        # Get tool definitions
        tool_definitions = tools_instance.get_tool_definitions()
        
        # Build prompts
        system_prompt = self._build_system_prompt(config)
        user_message = self._build_user_message()
        
        # Run agentic workflow
        result, conversation, error = await agentic_llm_client.run_agentic_workflow(
            system_prompt=system_prompt,
            user_message=user_message,
            tools=tool_definitions,
            tool_executor=tools_instance,
            max_iterations=15
        )
        
        if error:
            logger.error(f"Agentic planning failed: {error}")
            return None, error
        
        if not result:
            logger.error("No result from agentic workflow")
            return None, "LLM did not return a valid meal plan"
        
        # Validate result structure
        if "meals" not in result:
            logger.error("Result missing 'meals' field")
            return None, "Invalid meal plan format"
        
        logger.info(f"Agentic planning complete: {len(result['meals'])} meals planned")
        
        return result, None


# Global instance
agentic_meal_planner = None  # Will be initialized with pantry + recipe_crud