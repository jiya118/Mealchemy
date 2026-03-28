"""
LLM Recipe Service - Generates recipes using Groq or Gemini APIs.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from groq import Groq, APIError as GroqAPIError, APITimeoutError
import google.generativeai as genai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple rate limiter."""
    def __init__(self, requests_per_minute: int = 25):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self.last_request_time = None
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            if self.last_request_time is not None:
                elapsed = datetime.now().timestamp() - self.last_request_time
                wait_time = self.min_interval - elapsed
                if wait_time > 0:
                    logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
            self.last_request_time = datetime.now().timestamp()

class LLMRecipeService:
    """Service for generating recipes using selected LLM provider."""
    
    def __init__(
        self,
        provider: str = "groq",
        groq_api_key: str = "",
        gemini_api_key: str = "",
        model: str = ""
    ):
        """Initialize LLM service."""
        self.provider = provider.lower()
        self.rate_limiter = RateLimiter(requests_per_minute=25)
        
        if self.provider == "groq":
            self.model = model or "llama-3.3-70b-versatile"
            self.client = Groq(api_key=groq_api_key)
            logger.info(f"LLMRecipeService initialized with Groq model: {self.model}")
        elif self.provider == "gemini":
            self.model_name = model or "gemini-2.0-flash"
            genai.configure(api_key=gemini_api_key)
            self.gemini_model = genai.GenerativeModel(self.model_name)
            logger.info(f"LLMRecipeService initialized with Gemini model: {self.model_name}")
        else:
            raise ValueError(f"Unsupported MEAL_PLANNER_PROVIDER: {self.provider}")
    
    def _build_prompt(
        self,
        available_ingredients: List[str],
        diet_type: str,
        meal_type: str = "dinner",
        exclude_recipes: Optional[List[str]] = None
    ) -> str:
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
                f"{', '.join(exclude_recipes[:10])}."
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
        cleaned = response_text.strip()
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

        for field in ('recipe_name', 'main_ingredients'):
            if field not in data:
                raise ValueError(f"LLM response missing field: '{field}'")

        if not isinstance(data['recipe_name'], str) or not data['recipe_name'].strip():
            raise ValueError("'recipe_name' must be a non-empty string")

        if not isinstance(data['main_ingredients'], list):
            raise ValueError("'main_ingredients' must be a list")

        data['main_ingredients'] = [
            str(i).strip() for i in data['main_ingredients'] if str(i).strip()
        ]

        return data
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _call_llm(self, prompt: str) -> str:
        await self.rate_limiter.acquire()
        
        if self.provider == "groq":
            try:
                logger.debug("Calling Groq API")
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=400,
                    timeout=30.0
                )
                if not completion.choices or len(completion.choices) == 0:
                    raise ValueError("Empty response from Groq")
                response_text = completion.choices[0].message.content
                if not response_text:
                    raise ValueError("Empty content in response")
                logger.debug(f"Received response: {response_text[:100]}...")
                return response_text
            except Exception as e:
                logger.error(f"Groq API error: {e}")
                raise ValueError(f"Groq error: {str(e)}")
                
        elif self.provider == "gemini":
            try:
                logger.debug("Calling Gemini API")
                response = self.gemini_model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.7, "response_mime_type": "application/json"}
                )
                response_text = response.text
                if not response_text:
                    raise ValueError("Empty content in response")
                logger.debug(f"Received response: {response_text[:100]}...")
                return response_text
            except Exception as e:
                logger.error(f"Unexpected Gemini error: {e}")
                raise ValueError(f"Unexpected error: {str(e)}")
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def suggest_recipe(
        self,
        available_ingredients: List[str],
        diet_type: str = 'standard',
        meal_type: str = 'dinner',
        exclude_recipes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        logger.info(
            f"Suggesting {meal_type} recipe with {len(available_ingredients)} "
            f"ingredients, diet={diet_type}, provider={self.provider}"
        )
        prompt = self._build_prompt(
            available_ingredients=available_ingredients,
            diet_type=diet_type,
            meal_type=meal_type,
            exclude_recipes=exclude_recipes,
        )
        response_text = await self._call_llm(prompt)
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
                continue
        logger.info(f"Successfully generated {len(recipes)}/{len(ingredient_batches)} recipes")
        return recipes