"""
Intelligent Pantry Selector - Selects optimal ingredients for LLM meal planning.

Strategies:
1. Prioritize expiring items
2. Balance: majority vegetables, protein, carbs
3. Group into batches of ~10 items
4. Exclude spices/condiments
5. Use remaining items after each meal deduction
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class IntelligentPantrySelector:
    """
    Selects optimal ingredients from pantry for LLM meal planning.
    
    Smart selection based on expiry, balance, and availability.
    """
    
    # Spices and condiments to exclude
    EXCLUDED_CATEGORIES = {
        'salt', 'pepper', 'oil', 'sugar', 'flour', 'spice', 'spices',
        'seasoning', 'condiment', 'sauce', 'vinegar', 'soy sauce',
        'ketchup', 'mayo', 'mustard', 'honey', 'syrup', 'extract',
        'baking powder', 'baking soda', 'yeast', 'vanilla', 'cinnamon',
        'cumin', 'turmeric', 'paprika', 'chili powder', 'oregano',
        'basil', 'thyme', 'rosemary', 'garam masala', 'curry powder'
    }
    
    PROTEIN_KEYWORDS = {
        'chicken', 'beef', 'pork', 'lamb', 'fish', 'salmon', 'tuna',
        'shrimp', 'prawns', 'egg', 'eggs', 'paneer', 'tofu', 'dal',
        'lentil', 'chickpea', 'bean', 'beans', 'turkey', 'mutton'
    }
    
    CARB_KEYWORDS = {
        'rice', 'pasta', 'noodles', 'bread', 'roti', 'chapati',
        'potato', 'potatoes', 'quinoa', 'oats', 'couscous',
        'wheat', 'barley', 'poha', 'upma'
    }
    
    VEGETABLE_KEYWORDS = {
        'tomato', 'onion', 'garlic', 'ginger', 'carrot', 'spinach',
        'broccoli', 'cauliflower', 'cabbage', 'pepper', 'bell pepper',
        'mushroom', 'zucchini', 'eggplant', 'cucumber', 'lettuce',
        'kale', 'celery', 'corn', 'peas', 'bean', 'beans'
    }
    
    def __init__(self, pantry_items: List[Dict[str, Any]]):
        """
        Initialize selector with pantry items.
        
        Args:
            pantry_items: List of pantry item dicts with keys:
                - name: str
                - quantity: float
                - unit: str
                - category: str (optional)
                - expiry_date: str/datetime (optional)
        """
        self.pantry_items = pantry_items
        self.filtered_items = self._filter_valid_items()
        
        logger.info(f"Initialized with {len(pantry_items)} items, "
                   f"{len(self.filtered_items)} after filtering")
    
    def _filter_valid_items(self) -> List[Dict[str, Any]]:
        """Remove spices, condiments, and items with zero quantity."""
        filtered = []
        
        for item in self.pantry_items:
            # Skip if no quantity
            quantity = item.get('quantity', 0)
            if quantity <= 0:
                continue
            
            # Skip if excluded category
            name_lower = item.get('name', '').lower()
            category_lower = item.get('category', '').lower()
            
            is_excluded = any(
                excluded in name_lower or excluded in category_lower
                for excluded in self.EXCLUDED_CATEGORIES
            )
            
            if is_excluded:
                logger.debug(f"Excluding: {item.get('name')} (spice/condiment)")
                continue
            
            filtered.append(item)
        
        return filtered
    
    def _categorize_item(self, item: Dict[str, Any]) -> str:
        """Categorize item as protein, carb, or vegetable."""
        name_lower = item.get('name', '').lower()
        
        if any(protein in name_lower for protein in self.PROTEIN_KEYWORDS):
            return 'protein'
        
        if any(carb in name_lower for carb in self.CARB_KEYWORDS):
            return 'carb'
        
        if any(veg in name_lower for veg in self.VEGETABLE_KEYWORDS):
            return 'vegetable'
        
        # Default to vegetable for unknowns
        return 'vegetable'
    
    def _get_days_until_expiry(self, item: Dict[str, Any]) -> Optional[int]:
        """Calculate days until expiry."""
        expiry = item.get('expiry_date')
        
        if not expiry:
            return None
        
        # Convert to datetime if string
        if isinstance(expiry, str):
            try:
                expiry = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return None
        
        if not isinstance(expiry, datetime):
            return None
        
        # Calculate days
        now = datetime.now(expiry.tzinfo) if expiry.tzinfo else datetime.now()
        delta = (expiry - now).days
        
        return delta
    
    def _sort_by_priority(
        self, 
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sort items by priority:
        1. Expiring soon (< 7 days)
        2. Expiring medium (7-14 days)
        3. No expiry data
        4. Long shelf life (> 14 days)
        """
        def priority_key(item: Dict[str, Any]) -> tuple:
            days = self._get_days_until_expiry(item)
            
            if days is None:
                return (2, 0)  # No expiry data - medium priority
            
            if days < 0:
                return (4, days)  # Expired - lowest priority
            
            if days <= 7:
                return (0, days)  # Expiring soon - highest priority
            
            if days <= 14:
                return (1, days)  # Expiring medium - high priority
            
            return (3, days)  # Long shelf life - low priority
        
        return sorted(items, key=priority_key)
    
    def select_ingredients_for_day(
        self,
        max_items: int = 10,
        target_vegetables: int = 6,
        target_proteins: int = 2,
        target_carbs: int = 2
    ) -> List[str]:
        """
        Select optimal ingredients for a single day's meal planning.
        
        Args:
            max_items: Maximum ingredients to select
            target_vegetables: Target number of vegetables
            target_proteins: Target number of proteins
            target_carbs: Target number of carbs
            
        Returns:
            List of ingredient names
        """
        if len(self.filtered_items) == 0:
            logger.warning("No valid items in pantry")
            return []
        
        # If pantry is very low, just return everything
        if len(self.filtered_items) <= 5:
            logger.info("Low pantry stock, returning all items")
            return [item['name'] for item in self.filtered_items]
        
        # Categorize items
        proteins = []
        carbs = []
        vegetables = []
        
        for item in self.filtered_items:
            category = self._categorize_item(item)
            
            if category == 'protein':
                proteins.append(item)
            elif category == 'carb':
                carbs.append(item)
            else:
                vegetables.append(item)
        
        # Sort each category by priority
        proteins = self._sort_by_priority(proteins)
        carbs = self._sort_by_priority(carbs)
        vegetables = self._sort_by_priority(vegetables)
        
        logger.info(f"Categorized: {len(proteins)} proteins, "
                   f"{len(carbs)} carbs, {len(vegetables)} vegetables")
        
        # Select items based on targets
        selected = []
        
        # Add proteins (prioritize expiring)
        for item in proteins[:target_proteins]:
            selected.append(item['name'])
        
        # Add carbs
        for item in carbs[:target_carbs]:
            selected.append(item['name'])
        
        # Add vegetables
        for item in vegetables[:target_vegetables]:
            selected.append(item['name'])
        
        # If we need more items, fill from remaining
        if len(selected) < max_items:
            remaining = []
            
            for item in proteins[target_proteins:]:
                remaining.append(item)
            for item in carbs[target_carbs:]:
                remaining.append(item)
            for item in vegetables[target_vegetables:]:
                remaining.append(item)
            
            # Sort remaining by expiry
            remaining = self._sort_by_priority(remaining)
            
            for item in remaining:
                if len(selected) >= max_items:
                    break
                if item['name'] not in selected:
                    selected.append(item['name'])
        
        logger.info(f"Selected {len(selected)} ingredients for LLM")
        
        return selected[:max_items]
    
    def deduct_ingredients(
        self,
        recipe_ingredients: List[Dict[str, Any]],
        servings: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Deduct recipe ingredients from virtual pantry.
        
        Args:
            recipe_ingredients: List with keys: name, quantity, unit
            servings: Number of servings to deduct for
            
        Returns:
            List of deducted ingredients
        """
        deducted = []
        
        for recipe_ing in recipe_ingredients:
            ing_name = recipe_ing.get('name', '').lower()
            ing_quantity = recipe_ing.get('quantity', 0) * servings
            
            # Find matching pantry item
            for pantry_item in self.filtered_items:
                pantry_name = pantry_item.get('name', '').lower()
                
                # Simple name matching (can be enhanced)
                if ing_name in pantry_name or pantry_name in ing_name:
                    current_qty = pantry_item.get('quantity', 0)
                    
                    # Deduct quantity
                    deduct_qty = min(ing_quantity, current_qty)
                    pantry_item['quantity'] = current_qty - deduct_qty
                    
                    deducted.append({
                        'name': pantry_item['name'],
                        'quantity_deducted': deduct_qty,
                        'unit': pantry_item.get('unit', ''),
                        'remaining': pantry_item['quantity']
                    })
                    
                    logger.debug(f"Deducted {deduct_qty} of {pantry_item['name']}")
                    break
        
        # Re-filter items (remove zero quantity)
        self.filtered_items = [
            item for item in self.filtered_items 
            if item.get('quantity', 0) > 0
        ]
        
        logger.info(f"Deducted {len(deducted)} ingredients, "
                   f"{len(self.filtered_items)} items remaining")
        
        return deducted
    
    def get_remaining_items_count(self) -> int:
        """Get count of remaining valid items."""
        return len(self.filtered_items)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current pantry state."""
        proteins = []
        carbs = []
        vegetables = []
        expiring_soon = []
        
        for item in self.filtered_items:
            category = self._categorize_item(item)
            
            if category == 'protein':
                proteins.append(item['name'])
            elif category == 'carb':
                carbs.append(item['name'])
            else:
                vegetables.append(item['name'])
            
            # Check expiry
            days = self._get_days_until_expiry(item)
            if days is not None and 0 <= days <= 7:
                expiring_soon.append({
                    'name': item['name'],
                    'days_until_expiry': days
                })
        
        return {
            'total_items': len(self.filtered_items),
            'proteins': proteins,
            'carbs': carbs,
            'vegetables': vegetables,
            'expiring_soon': expiring_soon
        }