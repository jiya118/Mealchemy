"""
Pantry analyzer for virtual pantry management and ingredient tracking.
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from copy import deepcopy
import logging

from app.schema.pantryItem import PantryItemResponse
from app.schema.meal_plan import RecipeIngredient

logger = logging.getLogger(__name__)


class PantryAnalyzer:
    """Analyzes pantry inventory and manages virtual pantry for meal planning."""
    
    def __init__(self, pantry_items: List[PantryItemResponse]):
        """
        Initialize with current pantry inventory.
        
        Args:
            pantry_items: List of pantry items from database
        """
        self.real_pantry = pantry_items
        self.virtual_pantry: Dict[str, Dict[str, Any]] = {}
        self._initialize_virtual_pantry()
    
    def _initialize_virtual_pantry(self):
        """Create virtual pantry from real pantry items."""
        for item in self.real_pantry:
            self.virtual_pantry[item.name.lower()] = {
                "id": item.id,
                "name": item.name,
                "original_name": item.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "category": item.category,
                "expiry_date": item.expiry_date,
                "location": item.location
            }
        
        logger.info(f"Initialized virtual pantry with {len(self.virtual_pantry)} items")
    
    def create_virtual_pantry(self) -> Dict[str, Dict[str, Any]]:
        """
        Create a fresh copy of the virtual pantry.
        
        Returns:
            Deep copy of virtual pantry
        """
        return deepcopy(self.virtual_pantry)
    
    def get_available_ingredients(self) -> List[str]:
        """
        Get list of available ingredient names.
        
        Returns:
            List of ingredient names with quantity > 0
        """
        return [
            item["name"]
            for item in self.virtual_pantry.values()
            if item["quantity"] > 0
        ]
    
    def get_expiring_items(self, days: int = 7) -> Dict[str, int]:
        """
        Get items expiring within specified days.
        
        Args:
            days: Number of days to look ahead
            
        Returns:
            Dict mapping item name to days until expiry
        """
        cutoff_date = datetime.utcnow() + timedelta(days=days)
        expiring = {}
        
        for name, item in self.virtual_pantry.items():
            if item["expiry_date"]:
                # Handle both datetime and date objects
                expiry_date = item["expiry_date"]
                if isinstance(expiry_date, datetime):
                    expiry_datetime = expiry_date
                else:
                    expiry_datetime = datetime.combine(expiry_date, datetime.min.time())
                
                if datetime.utcnow() <= expiry_datetime <= cutoff_date:
                    days_until_expiry = (expiry_datetime - datetime.utcnow()).days
                    expiring[name] = days_until_expiry
        
        logger.info(f"Found {len(expiring)} items expiring in next {days} days")
        return expiring
    
    def check_ingredient_availability(
        self,
        ingredient_name: str,
        required_quantity: float = 0
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if an ingredient is available in sufficient quantity.
        
        Args:
            ingredient_name: Name of ingredient to check
            required_quantity: Minimum quantity needed
            
        Returns:
            Tuple of (is_available, item_details)
        """
        # Normalize ingredient name for matching
        normalized_name = ingredient_name.lower().strip()
        
        # Direct match
        if normalized_name in self.virtual_pantry:
            item = self.virtual_pantry[normalized_name]
            is_available = item["quantity"] >= required_quantity
            return is_available, item
        
        # Partial match (e.g., "tomatoes" matches "cherry tomatoes")
        for name, item in self.virtual_pantry.items():
            if normalized_name in name or name in normalized_name:
                is_available = item["quantity"] >= required_quantity
                return is_available, item
        
        return False, None
    
    def deduct_ingredients(
        self,
        ingredients: List[RecipeIngredient],
        servings_multiplier: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Deduct recipe ingredients from virtual pantry.
        
        Args:
            ingredients: List of ingredients to deduct
            servings_multiplier: Multiply quantities by this factor
            
        Returns:
            List of deducted items with details
        """
        deducted = []
        
        for ingredient in ingredients:
            if not ingredient.from_pantry:
                continue
            
            normalized_name = ingredient.name.lower().strip()
            quantity_to_deduct = ingredient.quantity * servings_multiplier
            
            # Try to find and deduct
            if normalized_name in self.virtual_pantry:
                item = self.virtual_pantry[normalized_name]
                actual_deduction = min(quantity_to_deduct, item["quantity"])
                item["quantity"] -= actual_deduction
                
                deducted.append({
                    "name": ingredient.name,
                    "deducted": actual_deduction,
                    "unit": ingredient.unit,
                    "remaining": item["quantity"]
                })
                
                logger.debug(f"Deducted {actual_deduction} {ingredient.unit} of {ingredient.name}")
        
        return deducted
    
    def get_missing_ingredients(
        self,
        recipe_ingredients: List[RecipeIngredient]
    ) -> List[RecipeIngredient]:
        """
        Identify ingredients missing from pantry.
        
        Args:
            recipe_ingredients: Ingredients needed for recipe
            
        Returns:
            List of missing ingredients
        """
        missing = []
        
        for ingredient in recipe_ingredients:
            is_available, _ = self.check_ingredient_availability(
                ingredient.name,
                ingredient.quantity
            )
            
            if not is_available:
                missing.append(ingredient)
        
        return missing
    
    def calculate_match_score(
        self,
        recipe_ingredients: List[RecipeIngredient],
        expiring_items: Dict[str, int],
        day_num: int = 0
    ) -> float:
        """
        Calculate how well a recipe matches available pantry items.
        
        Args:
            recipe_ingredients: Ingredients needed by recipe
            expiring_items: Items expiring soon with days until expiry
            day_num: Day number in the week (0-6)
            
        Returns:
            Match score (0-100)
        """
        if not recipe_ingredients:
            return 0.0
        
        # Base score: ingredient availability
        available_count = 0
        for ingredient in recipe_ingredients:
            is_available, _ = self.check_ingredient_availability(
                ingredient.name,
                ingredient.quantity
            )
            if is_available:
                available_count += 1
        
        base_score = (available_count / len(recipe_ingredients)) * 100
        
        # Expiry urgency boost
        expiry_boost = 0.0
        for ingredient in recipe_ingredients:
            normalized_name = ingredient.name.lower().strip()
            if normalized_name in expiring_items:
                days_until_expiry = expiring_items[normalized_name]
                urgency = max(0, 7 - days_until_expiry)  # More urgent = higher
                expiry_boost += urgency * 3
        
        # Boost expiring items early in the week
        if day_num < 3:  # Monday, Tuesday, Wednesday
            expiry_boost *= 1.5
        
        # Penalty for missing ingredients
        missing_count = len(recipe_ingredients) - available_count
        missing_penalty = missing_count * 8
        
        # Calculate final score
        final_score = base_score + expiry_boost - missing_penalty
        
        # Clamp to 0-100 range
        return max(0.0, min(100.0, final_score))
    
    def get_pantry_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of current virtual pantry.
        
        Returns:
            Summary with counts, categories, etc.
        """
        total_items = len(self.virtual_pantry)
        items_with_stock = sum(1 for item in self.virtual_pantry.values() if item["quantity"] > 0)
        
        categories = {}
        for item in self.virtual_pantry.values():
            category = item.get("category", "other")
            categories[category] = categories.get(category, 0) + 1
        
        return {
            "total_items": total_items,
            "items_with_stock": items_with_stock,
            "items_depleted": total_items - items_with_stock,
            "categories": categories
        }
    
    def reset_virtual_pantry(self):
        """Reset virtual pantry to match real pantry."""
        self._initialize_virtual_pantry()
        logger.info("Virtual pantry reset to real pantry state")
    
    def get_low_stock_items(self, threshold: float = 1.0) -> List[Dict[str, Any]]:
        """
        Get items with low stock.
        
        Args:
            threshold: Quantity threshold
            
        Returns:
            List of low stock items
        """
        low_stock = [
            item for item in self.virtual_pantry.values()
            if 0 < item["quantity"] <= threshold
        ]
        
        return sorted(low_stock, key=lambda x: x["quantity"])