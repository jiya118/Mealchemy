"""
Recipe Scorer - Scores recipes based on expiry urgency and pantry match.

Ensures expiring items are prioritized and recipes are ranked by quality.
"""
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RecipeScorer:
    """
    Scores recipes to prioritize expiring ingredients and good pantry matches.
    """
    
    def __init__(self, virtual_pantry: Dict[str, Dict], expiring_items: List[Dict]):
        """
        Initialize scorer.
        
        Args:
            virtual_pantry: Current pantry state {name: {qty, unit, expires_in_days}}
            expiring_items: List of items expiring soon
        """
        self.virtual_pantry = virtual_pantry
        self.expiring_items = {item['name'].lower(): item['days_until_expiry'] 
                               for item in expiring_items}
    
    def score_recipe(self, recipe: Dict[str, Any], day_number: int = 0) -> Dict[str, Any]:
        """
        Score a recipe based on multiple factors.
        
        Args:
            recipe: Recipe dict
            day_number: Which day of the week (0=Monday, 6=Sunday)
            
        Returns:
            Dict with score and breakdown
        """
        score_breakdown = {
            'total_score': 0.0,
            'pantry_match_score': 0.0,
            'expiry_urgency_score': 0.0,
            'day_appropriateness_score': 0.0,
            'ingredient_count_penalty': 0.0,
        }
        
        # Extract ingredients
        ingredients = self._extract_ingredients(recipe)
        if not ingredients:
            return {**score_breakdown, 'total_score': 0.0}
        
        # Factor 1: Pantry match (0-40 points)
        match_score = self._calculate_pantry_match(ingredients)
        score_breakdown['pantry_match_score'] = match_score
        
        # Factor 2: Expiry urgency (0-40 points)
        expiry_score = self._calculate_expiry_urgency(ingredients, day_number)
        score_breakdown['expiry_urgency_score'] = expiry_score
        
        # Factor 3: Day appropriateness (0-15 points)
        day_score = self._calculate_day_appropriateness(recipe, day_number)
        score_breakdown['day_appropriateness_score'] = day_score
        
        # Factor 4: Penalty for too many ingredients (0 to -10 points)
        complexity_penalty = self._calculate_complexity_penalty(ingredients)
        score_breakdown['ingredient_count_penalty'] = complexity_penalty
        
        # Calculate total
        total = (match_score + expiry_score + day_score + complexity_penalty)
        score_breakdown['total_score'] = max(0.0, total)
        
        return score_breakdown
    
    def _extract_ingredients(self, recipe: Dict[str, Any]) -> List[str]:
        """Extract ingredient names from recipe."""
        ingredients = []
        
        # Try different formats
        if 'extendedIngredients' in recipe:
            ingredients = [ing.get('name', ing.get('nameClean', '')) 
                          for ing in recipe['extendedIngredients']]
        elif 'ingredients_summary' in recipe:
            ingredients = [ing.get('name', ing['name'] if isinstance(ing, dict) else str(ing))
                          for ing in recipe['ingredients_summary']]
        elif 'ingredients' in recipe:
            ingredients = [ing if isinstance(ing, str) else ing.get('name', '')
                          for ing in recipe['ingredients']]
        
        # Normalize
        return [ing.lower().strip() for ing in ingredients if ing]
    
    def _calculate_pantry_match(self, ingredients: List[str]) -> float:
        """
        Calculate how well recipe matches pantry.
        
        Returns score 0-40.
        """
        if not ingredients:
            return 0.0
        
        available_count = 0
        total_main_ingredients = 0
        
        for ing_name in ingredients:
            # Check if it's in pantry
            pantry_match = self._find_in_pantry(ing_name)
            
            if pantry_match:
                available_count += 1
            
            total_main_ingredients += 1
        
        if total_main_ingredients == 0:
            return 0.0
        
        # Calculate match percentage
        match_percentage = available_count / total_main_ingredients
        
        # Convert to 0-40 scale
        score = match_percentage * 40
        
        # Bonus for high match
        if match_percentage >= 0.8:  # 80%+ match
            score += 5
        
        return min(40.0, score)
    
    def _calculate_expiry_urgency(self, ingredients: List[str], day_number: int) -> float:
        """
        Calculate urgency score based on expiring ingredients.
        
        Returns score 0-40.
        """
        expiry_score = 0.0
        expiring_used_count = 0
        
        for ing_name in ingredients:
            # Check if ingredient is expiring
            if ing_name in self.expiring_items:
                days_left = self.expiring_items[ing_name]
                
                # More urgent = higher score
                # 0 days left = 10 points
                # 1 day left = 8 points
                # 2 days left = 6 points
                # 3 days left = 4 points
                urgency_points = max(0, 10 - (days_left * 2))
                
                # Double urgency if early in week (should use expiring items first!)
                if day_number < 3:  # Monday, Tuesday, Wednesday
                    urgency_points *= 1.5
                
                expiry_score += urgency_points
                expiring_used_count += 1
        
        # Cap at 40
        expiry_score = min(40.0, expiry_score)
        
        # Bonus for using multiple expiring items
        if expiring_used_count >= 2:
            expiry_score = min(40.0, expiry_score + 5)
        
        return expiry_score
    
    def _calculate_day_appropriateness(self, recipe: Dict[str, Any], day_number: int) -> float:
        """
        Score recipe appropriateness for the day of week.
        
        Weekdays (0-4): Prefer quick recipes
        Weekends (5-6): Can be elaborate
        
        Returns score 0-15.
        """
        cook_time = recipe.get('readyInMinutes', recipe.get('ready_in_minutes', 30))
        
        is_weekday = day_number < 5  # Monday-Friday
        
        if is_weekday:
            # Weekday: prefer quick (<= 30 min)
            if cook_time <= 30:
                return 15.0
            elif cook_time <= 45:
                return 10.0
            else:
                return 5.0  # Too long for weekday
        else:
            # Weekend: elaborate is fine
            if cook_time <= 60:
                return 15.0
            elif cook_time <= 90:
                return 12.0
            else:
                return 8.0
    
    def _calculate_complexity_penalty(self, ingredients: List[str]) -> float:
        """
        Penalize recipes with too many ingredients.
        
        Returns penalty 0 to -10.
        """
        count = len(ingredients)
        
        if count <= 8:
            return 0.0  # Simple recipes, no penalty
        elif count <= 12:
            return -2.0  # Moderate complexity
        elif count <= 15:
            return -5.0  # Getting complex
        else:
            return -10.0  # Too complex
    
    def _find_in_pantry(self, ingredient_name: str) -> bool:
        """Check if ingredient is in pantry with quantity > 0."""
        # Exact match
        if ingredient_name in self.virtual_pantry:
            return self.virtual_pantry[ingredient_name].get('qty', 0) > 0
        
        # Partial match
        for pantry_name in self.virtual_pantry.keys():
            if ingredient_name in pantry_name or pantry_name in ingredient_name:
                if self.virtual_pantry[pantry_name].get('qty', 0) > 0:
                    return True
        
        return False
    
    def score_and_rank_recipes(
        self, 
        recipes: List[Dict[str, Any]], 
        day_number: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Score all recipes and return sorted by score (highest first).
        
        Args:
            recipes: List of recipe dicts
            day_number: Day of week (0-6)
            
        Returns:
            Sorted list of recipes with scores attached
        """
        scored_recipes = []
        
        for recipe in recipes:
            score_data = self.score_recipe(recipe, day_number)
            
            # Attach score to recipe
            recipe_with_score = {
                **recipe,
                'score': score_data['total_score'],
                'score_breakdown': score_data
            }
            
            scored_recipes.append(recipe_with_score)
        
        # Sort by score (highest first)
        scored_recipes.sort(key=lambda r: r['score'], reverse=True)
        
        logger.info(f"Scored {len(recipes)} recipes for day {day_number}")
        if scored_recipes:
            logger.info(f"Top score: {scored_recipes[0]['score']:.1f} - "
                       f"{scored_recipes[0].get('title', scored_recipes[0].get('name'))}")
        
        return scored_recipes
