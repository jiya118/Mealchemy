"""
LLM client for ingredient matching and meal planning assistance.
Uses Groq API (free tier) with Llama 3.1.
"""
import httpx
import json
from typing import Dict, Any, List, Optional
import logging

from app.core.settings import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for LLM-powered meal planning features using Groq."""
    
    def __init__(self):
        self.base_url = "https://api.groq.com/openai/v1"
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL
        self.timeout = 30.0
    
    def _make_request(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        """
        Make request to Groq API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            
        Returns:
            Response text
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000  # Increased for meal planning
        }
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(f"Groq API error: {e.response.status_code} - {e.response.text}")
            return ""
        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            return ""
    
    def match_ingredient_to_pantry(
        self,
        recipe_ingredient: str,
        pantry_items: List[str]
    ) -> Dict[str, Any]:
        """
        Match a recipe ingredient to available pantry items.
        
        Args:
            recipe_ingredient: Ingredient needed by recipe (e.g., "cherry tomatoes")
            pantry_items: List of available pantry item names
            
        Returns:
            Dict with match, confidence, and substitution info
        """
        prompt = f"""You are a cooking assistant. A recipe needs "{recipe_ingredient}".

Available in pantry: {', '.join(pantry_items)}

Can any pantry item work as a substitute or match? Respond ONLY with valid JSON:
{{
    "match": "exact pantry item name or null",
    "confidence": 0.0-1.0,
    "can_substitute": true/false,
    "note": "brief explanation"
}}

If no good match exists, return: {{"match": null, "confidence": 0.0, "can_substitute": false, "note": "No suitable substitute"}}"""

        messages = [
            {"role": "system", "content": "You are a helpful cooking assistant. Always respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.2)
            # Extract JSON from response (handle markdown code blocks)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            result = json.loads(response.strip())
            return result
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM JSON response: {response}")
            return {
                "match": None,
                "confidence": 0.0,
                "can_substitute": False,
                "note": "Failed to analyze"
            }
    
    def suggest_substitution(
        self,
        missing_ingredient: str,
        available_items: List[str]
    ) -> Optional[Dict[str, str]]:
        """
        Suggest a substitution for a missing ingredient.
        
        Args:
            missing_ingredient: Ingredient not available
            available_items: What's available in pantry
            
        Returns:
            Substitution suggestion or None
        """
        prompt = f"""Recipe needs "{missing_ingredient}" but it's not available.

Available items: {', '.join(available_items[:20])}

Suggest the best substitute if possible. Respond with JSON:
{{
    "substitute": "item name",
    "how_to_use": "brief instruction",
    "confidence": 0.0-1.0
}}

If no good substitute: {{"substitute": null, "how_to_use": "", "confidence": 0.0}}"""

        messages = [
            {"role": "system", "content": "You are a cooking expert. Respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self._make_request(messages, temperature=0.3)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            result = json.loads(response.strip())
            if result.get("substitute"):
                return result
            return None
        except json.JSONDecodeError:
            logger.error(f"Failed to parse substitution response: {response}")
            return None
    
    def generate_shopping_note(
        self,
        recipe_name: str,
        missing_items: List[str],
        expiring_items: List[str]
    ) -> str:
        """
        Generate a friendly note explaining recipe choice and what to buy.
        
        Args:
            recipe_name: Name of the recipe
            missing_items: Items user needs to buy
            expiring_items: Items from pantry that are expiring soon
            
        Returns:
            Friendly explanation text
        """
        prompt = f"""Generate a brief, friendly note (2-3 sentences) for a meal plan.

Recipe: {recipe_name}
Using expiring items: {', '.join(expiring_items) if expiring_items else 'none'}
Need to buy: {', '.join(missing_items) if missing_items else 'nothing'}

Make it helpful and conversational. Focus on preventing waste if using expiring items."""

        messages = [
            {"role": "system", "content": "You are a friendly meal planning assistant."},
            {"role": "user", "content": prompt}
        ]
        
        response = self._make_request(messages, temperature=0.7)
        return response.strip()
    
    def analyze_ingredient_list(
        self,
        recipe_ingredients: List[str],
        pantry_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze how well recipe ingredients match pantry inventory.
        
        Args:
            recipe_ingredients: List of ingredient names from recipe
            pantry_items: List of pantry item dicts with 'name' field
            
        Returns:
            Analysis with matches, missing items, and substitution suggestions
        """
        pantry_names = [item.get("name", "") for item in pantry_items]
        
        matches = []
        missing = []
        
        for ingredient in recipe_ingredients:
            match_result = self.match_ingredient_to_pantry(ingredient, pantry_names)
            
            if match_result.get("can_substitute") and match_result.get("confidence", 0) > 0.6:
                matches.append({
                    "ingredient": ingredient,
                    "matched_to": match_result["match"],
                    "confidence": match_result["confidence"],
                    "note": match_result["note"]
                })
            else:
                missing.append(ingredient)
        
        return {
            "matches": matches,
            "missing": missing,
            "match_percentage": (len(matches) / len(recipe_ingredients) * 100) if recipe_ingredients else 0
        }


# Global LLM client instance
llm_client = LLMClient()