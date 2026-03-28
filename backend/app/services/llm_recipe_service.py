"""
LLM Recipe Service - Generates recipes using Groq API with intelligent prompting.

Features:
- Diet-aware prompting
- Rate limiting (Groq free tier: 30 req/min)
- Retry logic with exponential backoff
- Clean JSON parsing
- Token usage tracking
"""
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

from groq import Groq, APIError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple rate limiter for Groq API.
    
    Groq free tier limits:
    - 30 requests per minute
    - 14,400 requests per day
    """
    
    def __init__(self, requests_per_minute: int = 25):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Max requests per minute (default 25 for safety margin)
        """
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute  # seconds between requests
        self.last_request_time = None
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limit."""
        async with self._lock:
            if self.last_request_time is not None:
                elapsed = datetime.now().timestamp() - self.last_request_time
                wait_time = self.min_interval - elapsed
                
                if wait_time > 0:
                    logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
            
            self.last_request_time = datetime.now().timestamp()


class LLMRecipeService:
    """
    Service for generating recipes using Groq LLM.
    
    Integrates with Spoonacular for recipe details.
    """
    
    def __init__(
        self,
        groq_api_key: str,
        model: str = "llama-3.3-70b-versatile"
    ):
        """
        Initialize LLM service.
        
        Args:
            groq_api_key: Groq API key
            model: Model to use (default: llama-3.3-70b-versatile)
        """
        self.client = Groq(api_key=groq_api_key)
        self.model = model
        self.rate_limiter = RateLimiter(requests_per_minute=25)
        
        logger.info(f"LLMRecipeService initialized with model: {model}")
    
    def _build_prompt(
        self,
        available_ingredients: List[str],
        diet_type: str,
        meal_type: str = "dinner",
        exclude_recipes: Optional[List[str]] = None
    ) -> str:
        """
        Build a concise, token-efficient prompt for the LLM.

        The LLM returns:
        - recipe_name  : the dish name
        - main_ingredients : ALL key ingredients needed, EXCLUDING common spices
          (salt, pepper, oils, chili powder, cumin, turmeric, coriander,
           garam masala, paprika, sugar, garlic powder, onion powder, soy sauce,
           vinegar, bay leaves, cardamom, cloves, cinnamon, baking soda, yeast)
        """
        diet_descriptions = {
            'standard':     'any type of food',
            'vegetarian':   'no meat or fish, dairy and eggs allowed',
            'eggetarian':   'no meat or fish, eggs and dairy allowed',
            'vegan':        'no animal products at all',
            'pescatarian':  'fish allowed, no other meat',
            'keto':         'very low carb, high fat',
            'paleo':        'no grains, legumes, or dairy',
            'gluten_free':  'no wheat, barley, or rye',
            'dairy_free':   'no milk, cheese, or butter',
        }

        diet_desc = diet_descriptions.get(diet_type, 'any type of food')
        ingredients_str = ", ".join(available_ingredients)

        exclude_note = ""
        if exclude_recipes:
            exclude_note = (
                f"\nDo NOT suggest these recipes (already planned): "
                f"{', '.join(exclude_recipes[:10])}."  # cap list to save tokens
            )

        prompt = (
            f"You are a chef. Suggest ONE practical {meal_type} recipe.\n\n"
            f"Pantry: {ingredients_str}\n"
            f"Diet: {diet_type} ({diet_desc}){exclude_note}\n\n"
            f"Rules:\n"
            f"- Strictly follow the diet restriction\n"
            f"- Complete meal, 15-60 min prep\n"
            f"- Use the pantry ingredients where possible\n\n"
            f"Reply ONLY with this JSON (no markdown, no extra text):\n"
            f'{{\n'
            f'  "recipe_name": "Name Here",\n'
            f'  "main_ingredients": ["ingredient1", "ingredient2"]\n'
            f'}}\n\n'
            f"main_ingredients = every key ingredient the recipe needs, "
            f"EXCLUDING: salt, pepper, oil, chili powder, cumin, turmeric, "
            f"coriander, garam masala, paprika, sugar, garlic powder, soy sauce, "
            f"vinegar, baking soda, yeast, cardamom, cinnamon, cloves."
        )

        return prompt
    
    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse and validate LLM JSON response.

        Expected keys:
        - recipe_name (str)
        - main_ingredients (list[str])
        """
        cleaned = response_text.strip()

        # Strip markdown code fences if present
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {e}\nRaw: {cleaned[:200]}")
            raise ValueError(f"Invalid JSON from LLM: {e}")

        # Validate required fields
        for field in ('recipe_name', 'main_ingredients'):
            if field not in data:
                raise ValueError(f"LLM response missing field: '{field}'")

        if not isinstance(data['recipe_name'], str) or not data['recipe_name'].strip():
            raise ValueError("'recipe_name' must be a non-empty string")

        if not isinstance(data['main_ingredients'], list):
            raise ValueError("'main_ingredients' must be a list")

        # Ensure all ingredients are strings, drop blanks
        data['main_ingredients'] = [
            str(i).strip() for i in data['main_ingredients'] if str(i).strip()
        ]

        return data
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((APITimeoutError, APIError)),
        reraise=True,
    )
    async def _call_groq(self, prompt: str) -> str:
        """
        Call Groq API with retry logic.
        
        Args:
            prompt: Formatted prompt
            
        Returns:
            LLM response text
            
        Raises:
            APITimeoutError: If request times out
            APIError: If API returns error
        """
        # Apply rate limiting
        await self.rate_limiter.acquire()
        
        try:
            logger.debug("Calling Groq API")
            
            # Make API call
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=400,   # trimmed from 1000 — response is now very short
                timeout=30.0
            )
            
            if not completion.choices or len(completion.choices) == 0:
                raise APIError("Empty response from Groq")
            
            response_text = completion.choices[0].message.content
            
            if not response_text:
                raise APIError("Empty content in response")
            
            # Log token usage if available
            if hasattr(completion, 'usage') and completion.usage:
                logger.info(
                    f"Groq tokens - Prompt: {completion.usage.prompt_tokens}, "
                    f"Completion: {completion.usage.completion_tokens}, "
                    f"Total: {completion.usage.total_tokens}"
                )
            
            logger.debug(f"Received response: {response_text[:100]}...")
            
            return response_text
        
        except APITimeoutError as e:
            logger.error(f"Groq API timeout: {e}")
            raise
        
        except APIError as e:
            logger.error(f"Groq API error: {e}")
            raise
        
        except Exception as e:
            logger.error(f"Unexpected Groq error: {e}")
            raise APIError(f"Unexpected error: {str(e)}")
    
    async def suggest_recipe(
        self,
        available_ingredients: List[str],
        diet_type: str = 'standard',
        meal_type: str = 'dinner',
        exclude_recipes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a recipe suggestion.

        Args:
            available_ingredients: Ingredient names from the virtual pantry
            diet_type: Diet restriction
            meal_type: breakfast / lunch / dinner
            exclude_recipes: Recipe names already planned (to avoid repeats)

        Returns:
            Dict with:
                - recipe_name (str)
                - main_ingredients (List[str])  ← all key ingredients, no spices
        """
        logger.info(
            f"Suggesting {meal_type} recipe with {len(available_ingredients)} "
            f"ingredients, diet={diet_type}"
        )

        prompt = self._build_prompt(
            available_ingredients=available_ingredients,
            diet_type=diet_type,
            meal_type=meal_type,
            exclude_recipes=exclude_recipes,
        )

        response_text = await self._call_groq(prompt)
        parsed = self._parse_llm_response(response_text)

        logger.info(
            f"LLM recipe: '{parsed['recipe_name']}' "
            f"({len(parsed['main_ingredients'])} main ingredients)"
        )
        return parsed
    
    async def suggest_multiple_recipes(
        self,
        ingredient_batches: List[List[str]],
        diet_type: str = 'standard',
        meal_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate multiple recipes for different days.
        
        Args:
            ingredient_batches: List of ingredient lists (one per day)
            diet_type: Diet restriction
            meal_types: List of meal types (one per batch)
            
        Returns:
            List of recipe dicts
        """
        if meal_types is None:
            meal_types = ['dinner'] * len(ingredient_batches)
        
        recipes = []
        used_recipe_names = []
        
        for i, (ingredients, meal_type) in enumerate(zip(ingredient_batches, meal_types)):
            logger.info(f"Generating recipe {i+1}/{len(ingredient_batches)}")
            
            try:
                recipe = await self.suggest_recipe(
                    available_ingredients=ingredients,
                    diet_type=diet_type,
                    meal_type=meal_type,
                    exclude_recipes=used_recipe_names
                )
                
                recipes.append(recipe)
                used_recipe_names.append(recipe['recipe_name'])
                
            except Exception as e:
                logger.error(f"Failed to generate recipe {i+1}: {e}")
                # Continue with next recipe
                continue
        
        logger.info(f"Successfully generated {len(recipes)}/{len(ingredient_batches)} recipes")
        
        return recipes