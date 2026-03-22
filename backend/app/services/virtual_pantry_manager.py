"""
Virtual Pantry Manager - Tracks ingredient usage across meal planning.

Clones real pantry and simulates ingredient deductions as recipes are selected.
"""
from typing import Dict, Any, List, Optional, Tuple
from copy import deepcopy
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class VirtualPantryManager:
    """
    Manages virtual pantry state during meal planning.
    """
    
    def __init__(self, real_pantry: List[Dict[str, Any]]):
        """
        Initialize with real pantry items.
        
        Args:
            real_pantry: List of dicts with keys: name, quantity, unit, category, expiry_date
        """
        self.real_pantry = real_pantry
        self.virtual_pantry = self._create_virtual_pantry()
        self.deduction_history = []
    
    def _create_virtual_pantry(self) -> Dict[str, Dict[str, Any]]:
        """
        Create virtual pantry dict from real pantry list.
        
        Returns:
            Dict mapping ingredient name (lowercase) to details
        """
        virtual = {}
        
        for item in self.real_pantry:
            if item.get('quantity', 0) <= 0:
                continue
            
            name_key = item['name'].lower().strip()
            
            # Calculate days until expiry
            days_until_expiry = None
            if item.get('expiry_date'):
                expiry = item['expiry_date']
                if isinstance(expiry, str):
                    try:
                        expiry = datetime.fromisoformat(expiry)
                    except:
                        expiry = None
                
                if expiry:
                    days_until_expiry = (expiry - datetime.utcnow()).days
            
            virtual[name_key] = {
                'name': item['name'],  # Original name
                'qty': float(item['quantity']),
                'unit': item.get('unit', ''),
                'category': item.get('category', 'other'),
                'expiry_date': item.get('expiry_date'),
                'days_until_expiry': days_until_expiry
            }
        
        logger.info(f"Created virtual pantry with {len(virtual)} items")
        return virtual
    
    def clone(self) -> 'VirtualPantryManager':
        """
        Create a deep copy of the current virtual pantry state.
        
        Returns:
            New VirtualPantryManager instance with cloned state
        """
        cloned = VirtualPantryManager(self.real_pantry)
        cloned.virtual_pantry = deepcopy(self.virtual_pantry)
        cloned.deduction_history = deepcopy(self.deduction_history)
        return cloned
    
    def can_make_recipe(self, recipe: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Check if recipe can be made with current virtual pantry.
        
        Args:
            recipe: Recipe dict with ingredients
            
        Returns:
            (can_make, missing_ingredients)
        """
        # Extract ingredients
        ingredients = self._extract_ingredients(recipe)
        
        missing = []
        
        for ing_name in ingredients:
            # Check if available in sufficient quantity
            if not self._has_ingredient(ing_name):
                missing.append(ing_name)
        
        can_make = len(missing) == 0
        
        return can_make, missing
    
    def deduct_ingredients(
        self, 
        recipe: Dict[str, Any], 
        day_name: str
    ) -> List[Dict[str, Any]]:
        """
        Deduct recipe ingredients from virtual pantry.
        
        Args:
            recipe: Recipe dict
            day_name: Name of day (for history tracking)
            
        Returns:
            List of deducted items with amounts
        """
        ingredients = self._extract_ingredients_with_amounts(recipe)
        
        deducted = []
        
        for ing_name, ing_qty, ing_unit in ingredients:
            # Find in pantry
            pantry_key = self._find_pantry_key(ing_name)
            
            if pantry_key:
                pantry_item = self.virtual_pantry[pantry_key]
                
                # Deduct quantity
                before_qty = pantry_item['qty']
                pantry_item['qty'] = max(0, pantry_item['qty'] - ing_qty)
                after_qty = pantry_item['qty']
                
                deducted.append({
                    'name': ing_name,
                    'deducted_qty': before_qty - after_qty,
                    'unit': ing_unit,
                    'remaining_qty': after_qty
                })
                
                logger.debug(f"Deducted {ing_name}: {before_qty} -> {after_qty} {ing_unit}")
        
        # Record in history
        self.deduction_history.append({
            'day': day_name,
            'recipe': recipe.get('title', recipe.get('name')),
            'deductions': deducted
        })
        
        return deducted
    
    def _extract_ingredients(self, recipe: Dict[str, Any]) -> List[str]:
        """Extract ingredient names only."""
        ingredients = []
        
        if 'extendedIngredients' in recipe:
            ingredients = [ing.get('name', ing.get('nameClean', ''))
                          for ing in recipe['extendedIngredients']]
        elif 'ingredients_summary' in recipe:
            for ing in recipe['ingredients_summary']:
                if isinstance(ing, dict):
                    ingredients.append(ing.get('name', ''))
                elif hasattr(ing, 'name'):
                    ingredients.append(ing.name)
                else:
                    ingredients.append(str(ing))
        elif 'ingredients' in recipe:
            for ing in recipe['ingredients']:
                if isinstance(ing, str):
                    ingredients.append(ing)
                elif isinstance(ing, dict):
                    ingredients.append(ing.get('name', ''))
                elif hasattr(ing, 'name'):
                    ingredients.append(ing.name)
        
        return [ing.lower().strip() for ing in ingredients if ing]
    
    def _extract_ingredients_with_amounts(
        self, 
        recipe: Dict[str, Any]
    ) -> List[Tuple[str, float, str]]:
        """
        Extract ingredients with quantities.
        
        Returns:
            List of (name, quantity, unit) tuples
        """
        ingredients = []
        
        if 'extendedIngredients' in recipe:
            for ing in recipe['extendedIngredients']:
                name = ing.get('name', ing.get('nameClean', '')).lower().strip()
                qty = float(ing.get('amount', 0))
                unit = ing.get('unit', '')
                if name:
                    ingredients.append((name, qty, unit))
        
        elif 'ingredients_summary' in recipe:
            for ing in recipe['ingredients_summary']:
                if isinstance(ing, dict):
                    name = ing.get('name', '').lower().strip()
                    qty = float(ing.get('quantity', 0))
                    unit = ing.get('unit', '')
                elif hasattr(ing, 'name'):
                    name = ing.name.lower().strip()
                    qty = float(getattr(ing, 'quantity', 0))
                    unit = getattr(ing, 'unit', '')
                else:
                    continue
                
                if name:
                    ingredients.append((name, qty, unit))
        
        return ingredients
    
    def _has_ingredient(self, ingredient_name: str, required_qty: float = 0) -> bool:
        """Check if ingredient is available."""
        pantry_key = self._find_pantry_key(ingredient_name)
        
        if pantry_key:
            return self.virtual_pantry[pantry_key]['qty'] > required_qty
        
        return False
    
    def _find_pantry_key(self, ingredient_name: str) -> Optional[str]:
        """Find pantry key for ingredient (handles partial matches)."""
        ingredient_name = ingredient_name.lower().strip()
        
        # Exact match
        if ingredient_name in self.virtual_pantry:
            return ingredient_name
        
        # Partial match
        for key in self.virtual_pantry.keys():
            if ingredient_name in key or key in ingredient_name:
                return key
        
        return None
    
    def get_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Get current state snapshot."""
        return {
            'items': deepcopy(self.virtual_pantry),
            'total_items': len(self.virtual_pantry),
            'items_with_stock': sum(1 for item in self.virtual_pantry.values() 
                                   if item['qty'] > 0)
        }
    
    def get_items_with_stock(self) -> Dict[str, Dict[str, Any]]:
        """Get only items with quantity > 0."""
        return {
            name: details 
            for name, details in self.virtual_pantry.items() 
            if details['qty'] > 0
        }
    
    def get_depleted_items(self) -> List[str]:
        """Get list of items that have been fully used."""
        return [
            name 
            for name, details in self.virtual_pantry.items() 
            if details['qty'] <= 0
        ]
    
    def format_for_llm(self, include_staples: bool = False) -> List[Dict[str, Any]]:
        """
        Format virtual pantry for LLM prompt.
        
        Args:
            include_staples: Whether to include staple ingredients
            
        Returns:
            List of dicts with compact format for LLM
        """
        formatted = []
        
        staples = {'salt', 'pepper', 'oil', 'water', 'sugar', 'flour'}
        
        for name, details in self.virtual_pantry.items():
            if details['qty'] <= 0:
                continue
            
            # Skip staples unless requested
            if not include_staples:
                if any(staple in name for staple in staples):
                    continue
            
            item_dict = {
                'name': details['name'],
                'qty': details['qty'],
                'unit': details['unit']
            }
            
            # Add expiry info if available
            if details['days_until_expiry'] is not None:
                item_dict['expires_in'] = details['days_until_expiry']
            
            formatted.append(item_dict)
        
        # Sort by expiry (soonest first)
        formatted.sort(key=lambda x: x.get('expires_in', 999))
        
        return formatted
    
    def get_deduction_summary(self) -> str:
        """Get human-readable summary of all deductions."""
        if not self.deduction_history:
            return "No deductions yet"
        
        lines = ["Ingredient Deduction History:"]
        for entry in self.deduction_history:
            lines.append(f"\n{entry['day']}: {entry['recipe']}")
            for deduction in entry['deductions']:
                lines.append(f"  - {deduction['name']}: "
                           f"-{deduction['deducted_qty']:.1f}{deduction['unit']} "
                           f"(remaining: {deduction['remaining_qty']:.1f})")
        
        return "\n".join(lines)
