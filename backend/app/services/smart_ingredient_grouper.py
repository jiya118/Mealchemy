"""
Smart Ingredient Grouper - Creates sensible ingredient combinations.

Prevents nonsense like "lemon, apple, banana, red chillies" by grouping
ingredients into logical categories and creating coherent combinations.
"""
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class IngredientGroup:
    """A logical group of ingredients that work well together."""
    proteins: List[str]
    vegetables: List[str]
    grains: List[str]
    name: str
    
    def to_search_string(self, max_ingredients: int = 5) -> str:
        """Convert group to comma-separated string for API search."""
        ingredients = []
        
        # Prioritize: proteins > vegetables > grains
        ingredients.extend(self.proteins[:2])
        ingredients.extend(self.vegetables[:2])
        ingredients.extend(self.grains[:1])
        
        return ",".join(ingredients[:max_ingredients])


class SmartIngredientGrouper:
    """
    Groups pantry ingredients into sensible combinations for recipe search.
    """
    
    # Ingredient categories - these make sense together in dishes
    PROTEINS = {
        'chicken', 'chicken breast', 'chicken thigh', 'chicken legs',
        'beef', 'ground beef', 'mutton', 'lamb',
        'fish', 'salmon', 'tuna', 'cod', 'prawns', 'shrimp',
        'eggs', 'egg',
        'paneer', 'tofu', 'tempeh',
        'lentils', 'dal', 'moong dal', 'toor dal', 'masoor dal',
        'chickpeas', 'chole', 'rajma', 'kidney beans',
        'black beans', 'pinto beans', 'white beans'
    }
    
    VEGETABLES = {
        'tomatoes', 'tomato', 'cherry tomatoes',
        'onions', 'onion', 'red onion', 'white onion',
        'garlic', 'ginger',
        'potatoes', 'potato', 'sweet potato',
        'carrots', 'carrot',
        'spinach', 'palak',
        'cauliflower', 'gobi',
        'peas', 'green peas',
        'bell peppers', 'capsicum', 'bell pepper',
        'broccoli', 'cabbage', 'lettuce',
        'eggplant', 'brinjal', 'aubergine',
        'zucchini', 'cucumber',
        'mushrooms', 'mushroom',
        'corn', 'green beans', 'okra', 'bhindi'
    }
    
    GRAINS_STARCHES = {
        'rice', 'basmati rice', 'brown rice',
        'pasta', 'spaghetti', 'penne', 'macaroni',
        'bread', 'wheat bread', 'whole wheat bread',
        'quinoa', 'couscous', 'bulgur',
        'noodles', 'ramen', 'udon',
        'oats', 'oatmeal'
    }
    
    # Items that should NOT be used as main search ingredients
    PANTRY_STAPLES = {
        # Spices
        'salt', 'pepper', 'black pepper', 'chili powder', 'turmeric',
        'cumin', 'coriander', 'garam masala', 'curry powder',
        'paprika', 'oregano', 'basil', 'thyme', 'cinnamon',
        
        # Oils/Fats
        'oil', 'olive oil', 'vegetable oil', 'ghee', 'butter',
        
        # Condiments
        'vinegar', 'soy sauce', 'ketchup', 'mustard',
        
        # Baking
        'sugar', 'flour', 'baking powder', 'baking soda',
        
        # Beverages
        'water', 'tea', 'coffee'
    }
    
    # Fruits (usually not main meal ingredients, avoid in combos)
    FRUITS = {
        'apple', 'apples', 'banana', 'bananas', 'orange', 'oranges',
        'lemon', 'lemons', 'lime', 'limes',
        'mango', 'mangoes', 'grapes', 'berries', 'strawberries'
    }
    
    def __init__(self, pantry_items: List[Dict[str, any]]):
        """
        Initialize with pantry items.
        
        Args:
            pantry_items: List of dicts with 'name', 'quantity', 'category', 'expiry_date'
        """
        self.pantry_items = pantry_items
        self.categorized = self._categorize_ingredients()
    
    def _normalize_name(self, name: str) -> str:
        """Normalize ingredient name for matching."""
        return name.lower().strip()
    
    def _categorize_ingredients(self) -> Dict[str, List[Dict]]:
        """
        Categorize pantry ingredients into proteins, vegetables, grains.
        
        Returns:
            Dict with 'proteins', 'vegetables', 'grains', 'others'
        """
        categorized = {
            'proteins': [],
            'vegetables': [],
            'grains': [],
            'fruits': [],
            'staples': [],
            'others': []
        }
        
        for item in self.pantry_items:
            if item.get('quantity', 0) <= 0:
                continue
            
            name = self._normalize_name(item['name'])
            
            # Skip staples
            if any(staple in name for staple in self.PANTRY_STAPLES):
                categorized['staples'].append(item)
                continue
            
            # Categorize by type
            if any(protein in name for protein in self.PROTEINS):
                categorized['proteins'].append(item)
            elif any(veg in name for veg in self.VEGETABLES):
                categorized['vegetables'].append(item)
            elif any(grain in name for grain in self.GRAINS_STARCHES):
                categorized['grains'].append(item)
            elif any(fruit in name for fruit in self.FRUITS):
                categorized['fruits'].append(item)
            else:
                categorized['others'].append(item)
        
        logger.info(f"Categorized pantry: {len(categorized['proteins'])} proteins, "
                   f"{len(categorized['vegetables'])} vegetables, "
                   f"{len(categorized['grains'])} grains")
        
        return categorized
    
    def _sort_by_expiry(self, items: List[Dict]) -> List[Dict]:
        """Sort items by expiry date (soonest first)."""
        def expiry_key(item):
            if not item.get('expiry_date'):
                return float('inf')  # No expiry = last
            
            from datetime import datetime
            expiry = item['expiry_date']
            if isinstance(expiry, str):
                try:
                    expiry = datetime.fromisoformat(expiry)
                except:
                    return float('inf')
            
            return (expiry - datetime.utcnow()).days
        
        return sorted(items, key=expiry_key)
    
    def create_smart_combinations(self, max_combos: int = 5) -> List[IngredientGroup]:
        """
        Create smart ingredient combinations for recipe search.
        
        Args:
            max_combos: Maximum number of combinations to create
            
        Returns:
            List of IngredientGroup objects
        """
        combinations = []
        
        # Sort each category by expiry
        proteins = self._sort_by_expiry(self.categorized['proteins'])
        vegetables = self._sort_by_expiry(self.categorized['vegetables'])
        grains = self._sort_by_expiry(self.categorized['grains'])
        
        # Strategy 1: Protein + Vegetables combos
        for i, protein in enumerate(proteins[:3]):  # Top 3 proteins
            # Get 2-3 vegetables that pair well
            veg_names = [v['name'] for v in vegetables[:3]]
            
            combo = IngredientGroup(
                proteins=[protein['name']],
                vegetables=veg_names,
                grains=[],
                name=f"combo_{i+1}_protein_veg"
            )
            combinations.append(combo)
            
            if len(combinations) >= max_combos:
                break
        
        # Strategy 2: Protein + Grain + Veg (complete meals)
        if len(combinations) < max_combos and grains:
            for i, protein in enumerate(proteins[:2]):
                for grain in grains[:2]:
                    combo = IngredientGroup(
                        proteins=[protein['name']],
                        vegetables=[v['name'] for v in vegetables[:2]],
                        grains=[grain['name']],
                        name=f"combo_complete_{i+1}"
                    )
                    combinations.append(combo)
                    
                    if len(combinations) >= max_combos:
                        break
                if len(combinations) >= max_combos:
                    break
        
        # Strategy 3: Vegetarian combos (if no/few proteins)
        if len(combinations) < max_combos:
            if vegetables and grains:
                combo = IngredientGroup(
                    proteins=[],
                    vegetables=[v['name'] for v in vegetables[:4]],
                    grains=[grains[0]['name']] if grains else [],
                    name="combo_vegetarian"
                )
                combinations.append(combo)
        
        logger.info(f"Created {len(combinations)} smart ingredient combinations")
        
        return combinations[:max_combos]
    
    def get_expiring_items(self, days_threshold: int = 3) -> List[Dict]:
        """
        Get items expiring within threshold days.
        
        Args:
            days_threshold: Number of days to look ahead
            
        Returns:
            List of items with their days until expiry
        """
        from datetime import datetime, timedelta
        
        expiring = []
        cutoff = datetime.utcnow() + timedelta(days=days_threshold)
        
        for item in self.pantry_items:
            if not item.get('expiry_date') or item.get('quantity', 0) <= 0:
                continue
            
            expiry = item['expiry_date']
            if isinstance(expiry, str):
                try:
                    expiry = datetime.fromisoformat(expiry)
                except:
                    continue
            
            if datetime.utcnow() <= expiry <= cutoff:
                days_left = (expiry - datetime.utcnow()).days
                expiring.append({
                    **item,
                    'days_until_expiry': days_left
                })
        
        # Sort by urgency
        expiring.sort(key=lambda x: x['days_until_expiry'])
        
        logger.info(f"Found {len(expiring)} items expiring in next {days_threshold} days")
        
        return expiring
    
    def get_main_ingredients_only(self) -> List[str]:
        """
        Get list of main ingredients (no staples, no fruits for main meals).
        
        Returns:
            List of ingredient names suitable for recipe search
        """
        main_ingredients = []
        
        # Include proteins, vegetables, grains
        for category in ['proteins', 'vegetables', 'grains']:
            for item in self.categorized[category]:
                main_ingredients.append(item['name'])
        
        logger.info(f"Extracted {len(main_ingredients)} main ingredients from pantry")
        
        return main_ingredients
    
    def validate_combination(self, ingredients: List[str]) -> bool:
        """
        Validate if an ingredient combination makes sense.
        
        Args:
            ingredients: List of ingredient names
            
        Returns:
            True if combination is sensible
        """
        normalized = [self._normalize_name(ing) for ing in ingredients]
        
        # Check 1: Not all fruits (smoothie territory)
        fruit_count = sum(1 for ing in normalized 
                         if any(fruit in ing for fruit in self.FRUITS))
        if fruit_count == len(normalized):
            logger.warning(f"Rejected all-fruit combination: {ingredients}")
            return False
        
        # Check 2: Not all staples
        staple_count = sum(1 for ing in normalized 
                          if any(staple in ing for staple in self.PANTRY_STAPLES))
        if staple_count == len(normalized):
            logger.warning(f"Rejected all-staple combination: {ingredients}")
            return False
        
        # Check 3: Should have at least one protein OR substantial veg
        has_protein = any(any(protein in ing for protein in self.PROTEINS) 
                         for ing in normalized)
        has_substantial_veg = any(any(veg in ing for veg in 
                                     {'potatoes', 'cauliflower', 'eggplant', 'chickpeas'})
                                 for ing in normalized)
        
        if not (has_protein or has_substantial_veg):
            logger.warning(f"Rejected weak combination (no protein/substantial veg): {ingredients}")
            return False
        
        return True
