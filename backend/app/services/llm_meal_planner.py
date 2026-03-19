"""
LLM-powered meal planner - Uses LLM to orchestrate weekly meal planning.
"""
import json
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import logging

from app.schema.recipe import (
    CachedRecipeResponse,
    LLMRecipeCandidate,
    LLMPantryItem,
    LLMWeeklyPlanResponse,
    LLMDayPlan,
    SimpleIngredient
)
from app.schema.pantryItem import PantryItemResponse
from app.schema.meal_plan import MealPlanConfig
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)


class LLMMealPlanner:
    """Uses LLM to intelligently plan weekly meals."""
    
    DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    
    def __init__(self):
        self.config: Optional[MealPlanConfig] = None
    
    def _prepare_pantry_for_llm(
        self,
        pantry_items: List[PantryItemResponse]
    ) -> List[LLMPantryItem]:
        """
        Convert pantry items to lightweight LLM format.
        
        Args:
            pantry_items: Full pantry items
            
        Returns:
            Lightweight pantry list for LLM
        """
        llm_pantry = []
        
        for item in pantry_items:
            if item.quantity and item.quantity > 0:
                expiry_str = None
                if item.expiry_date:
                    if isinstance(item.expiry_date, datetime):
                        expiry_str = item.expiry_date.strftime("%Y-%m-%d")
                    else:
                        expiry_str = str(item.expiry_date)
                
                llm_pantry.append(LLMPantryItem(
                    name=item.name,
                    qty=item.quantity,
                    unit=item.unit if item.unit else "",
                    expires=expiry_str
                ))
        
        return llm_pantry
    
    def _prepare_recipes_for_llm(
        self,
        recipes: List[CachedRecipeResponse]
    ) -> List[LLMRecipeCandidate]:
        """
        Convert cached recipes to lightweight LLM format.
        
        Args:
            recipes: Full cached recipes
            
        Returns:
            Lightweight recipe candidates for LLM
        """
        llm_recipes = []
        
        for recipe in recipes:
            llm_recipes.append(LLMRecipeCandidate(
                id=recipe.recipe_id,
                name=recipe.name,
                needs=recipe.ingredients_summary
            ))
        
        return llm_recipes
    
    def _build_llm_prompt(
        self,
        pantry: List[LLMPantryItem],
        recipes: List[LLMRecipeCandidate],
        config: MealPlanConfig
    ) -> str:
        """
        Build the LLM prompt for meal planning.
        
        Args:
            pantry: Lightweight pantry items
            recipes: Lightweight recipe candidates
            config: Meal plan configuration
            
        Returns:
            Complete prompt string
        """
        # Determine meal types based on meals_per_day
        meal_type = "dinner" if config.meals_per_day == 1 else "lunch and dinner"
        
        prompt = f"""You are a professional meal planner. Plan {config.days} days of {meal_type} for {config.servings} {"person" if config.servings == 1 else "people"}.

PANTRY (current stock):
{json.dumps([p.model_dump() for p in pantry], indent=2)}

AVAILABLE RECIPES:
{json.dumps([r.model_dump() for r in recipes], indent=2)}

REQUIREMENTS:
1. Diet: {config.diet_type}
2. Plan {config.days} days ({", ".join(self.DAY_NAMES[:config.days])})
3. Track pantry quantities - mentally deduct ingredients after each meal
4. CRITICAL: Prioritize items expiring soon (check "expires" field)
5. Maintain variety - don't repeat main ingredients within 3 days
6. If pantry runs low, note shopping items needed

INSTRUCTIONS:
- For each day, pick ONE recipe from available recipes
- Track remaining pantry after each selection
- Consider what's left for future days
- Items expiring in 2-3 days MUST be used first
- Provide brief reasoning for each choice
- List shopping items if needed

Respond ONLY with valid JSON in this EXACT format:
{{
  "monday": {{
    "recipe_id": "spoon_123456",
    "reasoning": "Uses tomatoes expiring in 2 days",
    "shopping_needed": []
  }},
  "tuesday": {{
    "recipe_id": "spoon_789012",
    "reasoning": "Different protein source for variety",
    "shopping_needed": [{{"name": "cream", "quantity": 200, "unit": "ml"}}]
  }}
  ... (continue for all {config.days} days)
}}

CRITICAL: Respond with ONLY the JSON object, no markdown, no explanations, no code blocks."""

        return prompt
    
    async def plan_week_with_llm(
        self,
        pantry_items: List[PantryItemResponse],
        recipe_candidates: List[CachedRecipeResponse],
        config: MealPlanConfig
    ) -> Tuple[Optional[LLMWeeklyPlanResponse], Optional[str]]:
        """
        Use LLM to plan the week.
        
        Args:
            pantry_items: Available pantry items
            recipe_candidates: Available recipe options
            config: Meal plan configuration
            
        Returns:
            Tuple of (LLM plan response, error message)
        """
        self.config = config
        
        # Prepare lightweight data
        llm_pantry = self._prepare_pantry_for_llm(pantry_items)
        llm_recipes = self._prepare_recipes_for_llm(recipe_candidates)
        
        if not llm_recipes:
            return None, "No recipe candidates available"
        
        # Build prompt
        prompt = self._build_llm_prompt(llm_pantry, llm_recipes, config)
        
        logger.info(f"Sending meal planning request to LLM (prompt size: {len(prompt)} chars)")
        
        try:
            # Call LLM
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional meal planner. You MUST respond ONLY with valid JSON, no markdown formatting, no code blocks."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = llm_client._make_request(messages, temperature=0.4)
            
            if not response:
                return None, "LLM returned empty response"
            
            # Parse JSON response
            response_text = response.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Remove first and last line (```json and ```)
                response_text = "\n".join(lines[1:-1])
            
            # Remove any leading/trailing whitespace
            response_text = response_text.strip()
            
            # Parse JSON
            plan_dict = json.loads(response_text)
            
            # Convert to Pydantic model
            llm_plan = LLMWeeklyPlanResponse(**plan_dict)
            
            logger.info("Successfully parsed LLM meal plan")
            
            return llm_plan, None
            
        except json.JSONDecodeError as e:
            error_msg = f"LLM returned invalid JSON: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"LLM response was: {response[:500]}")
            return None, error_msg
        
        except Exception as e:
            error_msg = f"LLM planning failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg
    
    def validate_llm_plan(
        self,
        llm_plan: LLMWeeklyPlanResponse,
        recipe_candidates: List[CachedRecipeResponse],
        days: int
    ) -> Tuple[bool, List[str]]:
        """
        Validate LLM's plan for basic correctness.
        
        Args:
            llm_plan: LLM's generated plan
            recipe_candidates: Available recipes
            days: Expected number of days
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        recipe_ids = {r.recipe_id for r in recipe_candidates}
        
        # Check each day
        day_names = self.DAY_NAMES[:days]
        for day_name in day_names:
            day_plan = getattr(llm_plan, day_name, None)
            
            if not day_plan:
                errors.append(f"Missing plan for {day_name}")
                continue
            
            # Check if recipe_id is valid
            if day_plan.recipe_id not in recipe_ids:
                errors.append(f"{day_name}: Invalid recipe_id {day_plan.recipe_id}")
        
        # Validation is intentionally light - we trust LLM's logic
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(f"LLM plan validation failed: {errors}")
        
        return is_valid, errors


# Global instance
llm_meal_planner = LLMMealPlanner()