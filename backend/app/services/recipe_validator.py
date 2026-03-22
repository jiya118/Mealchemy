"""
Recipe Validator - Filters out garbage recipes (smoothies, chutneys, condiments).

Hard validation rules to ensure only actual MEALS get through.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class RecipeValidator:
    """
    Validates recipes to ensure they're actual meals, not smoothies/chutneys/etc.
    """
    
    # Keywords in title that indicate NON-MEAL recipes
    REJECT_TITLE_KEYWORDS = {
        # Beverages
        'smoothie', 'juice', 'drink', 'beverage', 'shake', 'lassi',
        'tea', 'coffee', 'lemonade', 'milkshake',
        
        # Condiments/Sauces
        'chutney', 'sauce', 'dip', 'salsa', 'relish', 'paste',
        'ketchup', 'mayo', 'mayonnaise', 'aioli',
        
        # Sides (unless substantial)
        'bread', 'naan', 'roti', 'chapati', 'paratha',
        'biscuit', 'cookie', 'cracker',
        
        # Snacks (not meals)
        'chips', 'popcorn', 'fries',
        
        # Desserts (unless specified)
        'cake', 'brownie', 'cookie', 'pudding', 'ice cream',
        
        # Toppings
        'topping', 'frosting', 'glaze', 'syrup'
    }
    
    # Salads are tricky - reject unless they have protein
    SALAD_EXCEPTIONS = {
        'chicken salad', 'tuna salad', 'egg salad', 'pasta salad',
        'bean salad', 'lentil salad', 'quinoa salad'
    }
    
    # Must have at least ONE of these to be considered a meal
    PROTEIN_INDICATORS = {
        'chicken', 'beef', 'pork', 'lamb', 'mutton', 'fish', 'salmon',
        'tuna', 'shrimp', 'prawns', 'egg', 'eggs',
        'lentils', 'dal', 'beans', 'chickpeas', 'tofu', 'paneer',
        'cheese'     # (in sufficient quantity)
    }
    
    # Substantial vegetables/grains that can be meal base
    SUBSTANTIAL_BASES = {
        'rice', 'pasta', 'noodles', 'quinoa', 'potatoes',
        'cauliflower' # (for cauliflower rice, etc.),
        'eggplant', 'zucchini' # (for boats/steaks)
    }
    
    def __init__(self, min_ingredients: int = 5, min_cook_time: int = 10):
        """
        Initialize validator.
        
        Args:
            min_ingredients: Minimum number of ingredients for a meal
            min_cook_time: Minimum cooking time in minutes (smoothies = instant)
        """
        self.min_ingredients = min_ingredients
        self.min_cook_time = min_cook_time
        
        # Diet-specific banned ingredients
        self.VEGAN_BANNED = {
            'paneer', 'cheese', 'milk', 'cream', 'butter', 'ghee',
            'egg', 'eggs', 'yogurt', 'curd', 'honey', 'gelatin',
            'whey', 'casein', 'lactose', 'dairy'
        }
        
        self.VEGETARIAN_BANNED = {
            'chicken', 'beef', 'pork', 'lamb', 'mutton', 'meat',
            'fish', 'salmon', 'tuna', 'shrimp', 'prawns', 'seafood',
            'bacon', 'ham', 'sausage', 'anchovy', 'anchovies'
        }
    
    def _check_diet_compliance(
        self, 
        recipe: Dict[str, Any], 
        diet_type: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if recipe complies with diet restrictions.
        
        Args:
            recipe: Recipe data
            diet_type: 'vegan', 'vegetarian', 'standard', etc.
            
        Returns:
            (is_valid, rejection_reason)
        """
        if not diet_type or diet_type == 'standard':
            return True, None
        
        # Get recipe title and ingredients
        title = recipe.get('title', recipe.get('name', '')).lower()
        
        # Get ingredients list
        ingredients = recipe.get('extendedIngredients', recipe.get('ingredients_summary', []))
        ingredient_names = []
        
        for ing in ingredients:
            if isinstance(ing, dict):
                name = ing.get('name', ing.get('nameClean', ''))
            else:
                name = getattr(ing, 'name', str(ing))
            
            if name:
                ingredient_names.append(name.lower())
        
        # Combine title and ingredients for checking
        all_text = title + ' ' + ' '.join(ingredient_names)
        
        # Check vegan restrictions
        if diet_type == 'vegan':
            for banned in self.VEGAN_BANNED:
                if banned in all_text:
                    return False, f"Contains non-vegan ingredient: {banned}"
        
        # Check vegetarian restrictions
        if diet_type in ['vegetarian', 'eggetarian']:
            for banned in self.VEGETARIAN_BANNED:
                if banned in all_text:
                    return False, f"Contains meat/fish: {banned}"
        
        return True, None
    
    def validate_recipe(
        self, 
        recipe: Dict[str, Any], 
        diet_type: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if recipe is an actual meal and complies with diet restrictions.
        
        Args:
            recipe: Recipe dict from Spoonacular or cache
            diet_type: Optional diet restriction
            
        Returns:
            (is_valid, rejection_reason)
        """
        title = recipe.get('title', recipe.get('name', '')).lower()
        
        # FIRST: Check diet compliance if specified
        if diet_type:
            is_compliant, reason = self._check_diet_compliance(recipe, diet_type)
            if not is_compliant:
                return False, reason
        
        # Check 1: Title keywords
        for keyword in self.REJECT_TITLE_KEYWORDS:
            if keyword in title:
                # Special case: salad with protein is OK
                if keyword == 'salad':
                    if any(exception in title for exception in self.SALAD_EXCEPTIONS):
                        break  # Allow this salad
                
                return False, f"Title contains '{keyword}' (non-meal indicator)"
        
        # Check 2: Minimum ingredients
        ingredients = recipe.get('extendedIngredients', 
                                recipe.get('ingredients', 
                                recipe.get('ingredients_summary', [])))
        
        if len(ingredients) < self.min_ingredients:
            return False, f"Too few ingredients ({len(ingredients)} < {self.min_ingredients})"
        
        # Check 3: Cooking time (smoothies/juices are instant)
        cook_time = recipe.get('readyInMinutes', recipe.get('ready_in_minutes', 0))
        if cook_time < self.min_cook_time:
            return False, f"Too quick to prepare ({cook_time}min < {self.min_cook_time}min, likely beverage)"
        
        # Check 4: Must have protein OR substantial base
        has_protein = self._check_has_protein(ingredients, title)
        has_substantial_base = self._check_has_substantial_base(ingredients, title)
        
        if not (has_protein or has_substantial_base):
            return False, "No protein or substantial meal base found"
        
        # Check 5: Recipe type (if available)
        dish_types = recipe.get('dishTypes', [])
        if dish_types:
            # If explicitly marked as condiment/beverage, reject
            if any(dtype in ['condiment', 'sauce', 'dip', 'beverage'] 
                   for dtype in dish_types):
                return False, f"Marked as {dish_types[0]} (not a meal)"
        
        # All checks passed
        return True, None
    
    def _check_has_protein(self, ingredients: List, title: str) -> bool:
        """Check if recipe has protein."""
        # Check in title
        if any(protein in title for protein in self.PROTEIN_INDICATORS):
            return True
        
        # Check in ingredients
        for ing in ingredients:
            # Handle different ingredient formats
            ing_name = ''
            if isinstance(ing, dict):
                ing_name = ing.get('name', ing.get('nameClean', 
                                   ing.get('original', ''))).lower()
            elif isinstance(ing, str):
                ing_name = ing.lower()
            else:
                # Handle Pydantic models
                ing_name = getattr(ing, 'name', '').lower()
            
            if any(protein in ing_name for protein in self.PROTEIN_INDICATORS):
                return True
        
        return False
    
    def _check_has_substantial_base(self, ingredients: List, title: str) -> bool:
        """Check if recipe has substantial base ingredient."""
        # Check in title
        if any(base in title for base in self.SUBSTANTIAL_BASES):
            return True
        
        # Check in ingredients
        for ing in ingredients:
            ing_name = ''
            if isinstance(ing, dict):
                ing_name = ing.get('name', ing.get('nameClean', 
                                   ing.get('original', ''))).lower()
            elif isinstance(ing, str):
                ing_name = ing.lower()
            else:
                ing_name = getattr(ing, 'name', '').lower()
            
            if any(base in ing_name for base in self.SUBSTANTIAL_BASES):
                return True
        
        return False
    
    def validate_batch(
        self, 
        recipes: List[Dict[str, Any]],
        diet_type: Optional[str] = None
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Validate a batch of recipes.
        
        Args:
            recipes: List of recipe dicts
            diet_type: Optional diet restriction to enforce
            
        Returns:
            (valid_recipes, rejected_recipes_with_reasons)
        """
        valid = []
        rejected = []
        
        for recipe in recipes:
            is_valid, reason = self.validate_recipe(recipe, diet_type=diet_type)
            
            if is_valid:
                valid.append(recipe)
            else:
                rejected.append({
                    'recipe': recipe,
                    'rejection_reason': reason
                })
                logger.debug(f"Rejected: {recipe.get('title', recipe.get('name'))} - {reason}")
        
        logger.info(f"Validation: {len(valid)} valid, {len(rejected)} rejected")
        
        return valid, rejected
    
    def get_validation_summary(self, rejected: List[Dict]) -> str:
        """
        Get human-readable summary of rejections.
        
        Args:
            rejected: List of rejected recipes with reasons
            
        Returns:
            Summary string
        """
        if not rejected:
            return "All recipes passed validation!"
        
        reason_counts = {}
        for item in rejected:
            reason = item['rejection_reason']
            # Extract main reason (before parentheses)
            main_reason = reason.split('(')[0].strip()
            reason_counts[main_reason] = reason_counts.get(main_reason, 0) + 1
        
        summary_lines = [f"Rejected {len(rejected)} recipes:"]
        for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
            summary_lines.append(f"  - {count}x {reason}")
        
        return "\n".join(summary_lines)