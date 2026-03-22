"""
Test Script - Demonstrates the complete single-shot meal planning workflow.

This shows how all components work together with realistic test data.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Mock implementations for testing without actual dependencies
class MockRecipeCacheManager:
    """Mock cache manager for testing."""
    
    async def find_cached_recipes(self, pantry_ingredients, diet_type=None, min_recipes=5):
        """Return mock cached recipes."""
        return [
            {
                'id': 'cache_1',
                'title': 'Chicken Curry',
                'readyInMinutes': 30,
                'extendedIngredients': [
                    {'name': 'chicken', 'amount': 200, 'unit': 'g'},
                    {'name': 'tomatoes', 'amount': 2, 'unit': ''},
                    {'name': 'onions', 'amount': 1, 'unit': ''},
                    {'name': 'curry powder', 'amount': 2, 'unit': 'tbsp'}
                ]
            },
            {
                'id': 'cache_2',
                'title': 'Spinach Dal',
                'readyInMinutes': 25,
                'extendedIngredients': [
                    {'name': 'lentils', 'amount': 150, 'unit': 'g'},
                    {'name': 'spinach', 'amount': 100, 'unit': 'g'},
                    {'name': 'garlic', 'amount': 3, 'unit': 'cloves'},
                    {'name': 'cumin', 'amount': 1, 'unit': 'tsp'}
                ]
            },
            {
                'id': 'cache_3',
                'title': 'Tomato Pasta',
                'readyInMinutes': 20,
                'extendedIngredients': [
                    {'name': 'pasta', 'amount': 200, 'unit': 'g'},
                    {'name': 'tomatoes', 'amount': 3, 'unit': ''},
                    {'name': 'garlic', 'amount': 2, 'unit': 'cloves'},
                    {'name': 'basil', 'amount': 5, 'unit': 'leaves'}
                ]
            },
            {
                'id': 'cache_4',
                'title': 'Egg Fried Rice',
                'readyInMinutes': 15,
                'extendedIngredients': [
                    {'name': 'rice', 'amount': 200, 'unit': 'g'},
                    {'name': 'eggs', 'amount': 2, 'unit': ''},
                    {'name': 'vegetables', 'amount': 100, 'unit': 'g'},
                    {'name': 'soy sauce', 'amount': 1, 'unit': 'tbsp'}
                ]
            },
            # BAD RECIPES (should be filtered out)
            {
                'id': 'bad_1',
                'title': 'Mango Smoothie',
                'readyInMinutes': 5,
                'extendedIngredients': [
                    {'name': 'mango', 'amount': 1, 'unit': ''},
                    {'name': 'milk', 'amount': 200, 'unit': 'ml'}
                ]
            },
            {
                'id': 'bad_2',
                'title': 'Mint Chutney',
                'readyInMinutes': 10,
                'extendedIngredients': [
                    {'name': 'mint', 'amount': 50, 'unit': 'g'},
                    {'name': 'lemon', 'amount': 1, 'unit': ''}
                ]
            }
        ]
    
    async def cache_spoonacular_recipe(self, recipe, diet_type=None):
        """Mock caching."""
        return recipe
    
    class recipe_crud:
        @staticmethod
        async def create(recipe):
            return recipe


class MockSpoonacularClient:
    """Mock Spoonacular client for testing."""
    
    def search_recipes_by_ingredients(self, ingredients, number=10, ranking=1, diet=None):
        """Mock search."""
        return [
            {'id': 12345, 'title': 'Grilled Chicken'},
            {'id': 67890, 'title': 'Vegetable Stir Fry'}
        ]
    
    def get_recipe_details(self, recipe_id):
        """Mock details fetch."""
        return {
            'id': recipe_id,
            'title': f'Recipe {recipe_id}',
            'readyInMinutes': 30,
            'extendedIngredients': [
                {'name': 'ingredient1', 'amount': 100, 'unit': 'g'},
                {'name': 'ingredient2', 'amount': 2, 'unit': ''}
            ]
        }


class MockLLMClient:
    """Mock LLM client for testing."""
    
    async def _make_request(self, messages, temperature=0.3):
        """Mock LLM response."""
        # Simulate LLM picking recipes
        plan = {
            'monday': {'recipe_id': 2, 'reason': 'Uses expiring spinach'},
            'tuesday': {'recipe_id': 1, 'reason': 'Different protein'},
            'wednesday': {'recipe_id': 3, 'reason': 'Quick weekday meal'},
            'thursday': {'recipe_id': 4, 'reason': 'Easy and fast'},
            'friday': {'recipe_id': 1, 'reason': 'End of week'},
            'saturday': {'recipe_id': 2, 'reason': 'Weekend meal'},
            'sunday': {'recipe_id': 3, 'reason': 'Light dinner'}
        }
        
        return json.dumps(plan)


class MockPantryItem:
    """Mock Pydantic model for testing."""
    def __init__(self, data: Dict):
        self.name = data['name']
        self.quantity = data['quantity']
        self.unit = data['unit']
        self.category = data['category']
        self.expiry_date = data['expiry_date']


# Test data
def create_test_pantry() -> List[Dict[str, Any]]:
    """Create realistic test pantry."""
    now = datetime.utcnow()
    
    return [
        # Expiring soon!
        {
            'name': 'Spinach',
            'quantity': 200,
            'unit': 'g',
            'category': 'vegetable',
            'expiry_date': (now + timedelta(days=1)).isoformat()
        },
        {
            'name': 'Chicken',
            'quantity': 500,
            'unit': 'g',
            'category': 'protein',
            'expiry_date': (now + timedelta(days=2)).isoformat()
        },
        
        # Good stock
        {
            'name': 'Tomatoes',
            'quantity': 6,
            'unit': 'count',
            'category': 'vegetable',
            'expiry_date': (now + timedelta(days=5)).isoformat()
        },
        {
            'name': 'Onions',
            'quantity': 4,
            'unit': 'count',
            'category': 'vegetable',
            'expiry_date': None
        },
        {
            'name': 'Garlic',
            'quantity': 10,
            'unit': 'cloves',
            'category': 'vegetable',
            'expiry_date': None
        },
        {
            'name': 'Rice',
            'quantity': 2,
            'unit': 'kg',
            'category': 'grain',
            'expiry_date': None
        },
        {
            'name': 'Pasta',
            'quantity': 500,
            'unit': 'g',
            'category': 'grain',
            'expiry_date': None
        },
        {
            'name': 'Lentils',
            'quantity': 300,
            'unit': 'g',
            'category': 'protein',
            'expiry_date': None
        },
        {
            'name': 'Eggs',
            'quantity': 6,
            'unit': 'count',
            'category': 'protein',
            'expiry_date': (now + timedelta(days=7)).isoformat()
        },
        
        # Staples (should be filtered in smart grouping)
        {
            'name': 'Salt',
            'quantity': 500,
            'unit': 'g',
            'category': 'spice',
            'expiry_date': None
        },
        {
            'name': 'Vegetable Oil',
            'quantity': 1,
            'unit': 'L',
            'category': 'oil',
            'expiry_date': None
        }
    ]


async def main():
    """Test the complete workflow."""
    print("=" * 60)
    print("SINGLE-SHOT MEAL PLAN GENERATOR - TEST")
    print("=" * 60)
    print()
    
    # Create test data
    pantry_items = create_test_pantry()
    
    print(f"Test Pantry: {len(pantry_items)} items")
    print(f"Expiring items:")
    for item in pantry_items:
        if item.get('expiry_date'):
            expiry = datetime.fromisoformat(item['expiry_date'])
            days_left = (expiry - datetime.utcnow()).days
            if days_left <= 3:
                print(f"  ⚠️  {item['name']}: {days_left} days left")
    print()
    
    # Initialize generator with mocks
    from app.services.single_shot_meal_planner import SingleShotMealPlanGenerator
    
    generator = SingleShotMealPlanGenerator(
        pantry_items=[MockPantryItem(item) for item in pantry_items],
        recipe_crud=MockRecipeCacheManager.recipe_crud
    )
    generator.cache_manager = MockRecipeCacheManager()
    generator.spoonacular_client = MockSpoonacularClient()
    generator.llm_client = MockLLMClient()
    
    # Generate meal plan
    print("Generating 7-day meal plan...")
    print()
    
    result = await generator.generate_meal_plan(
        days=7,
        diet_type='standard',
        servings=2
    )
    
    # Display results
    if result.get('success'):
        print("✅ MEAL PLAN GENERATED SUCCESSFULLY")
        print()
        
        print("=" * 60)
        print("WEEKLY MEAL PLAN")
        print("=" * 60)
        
        for meal in result['meals']:
            print(f"\n{meal['day'].upper()}")
            print(f"  Recipe: {meal['recipe_name']}")
            print(f"  Time: {meal['ready_in_minutes']} minutes")
            print(f"  Score: {meal.get('score', 'N/A')}")
            print(f"  Reason: {meal['reason']}")
            
            if meal.get('ingredients_from_pantry'):
                print(f"  From pantry: {', '.join(meal['ingredients_from_pantry'][:3])}")
        
        print()
        print("=" * 60)
        print("PANTRY SUMMARY")
        print("=" * 60)
        summary = result['pantry_summary']
        print(f"Items used: {summary['items_used']}")
        print(f"Items remaining: {summary['items_remaining']}")
        
        if result.get('deduction_history'):
            print()
            print("Deduction History:")
            for entry in result['deduction_history'][:3]:  # Show first 3
                print(f"  {entry['day']}: {entry['recipe']}")
                for deduction in entry['deductions'][:2]:
                    print(f"    - {deduction['name']}: "
                         f"{deduction['deducted_qty']:.1f}{deduction['unit']}")
        
    else:
        print("❌ MEAL PLAN GENERATION FAILED")
        print(f"Error: {result.get('error')}")
        print(f"Suggestion: {result.get('suggestion')}")
    
    print()
    print("=" * 60)
    print("COMPONENT TESTS")
    print("=" * 60)
    
    # Test smart grouping
    from app.services.smart_ingredient_grouper import SmartIngredientGrouper
    
    grouper = SmartIngredientGrouper(pantry_items)
    combos = grouper.create_smart_combinations(max_combos=3)
    
    print(f"\n✓ Smart Combinations ({len(combos)}):")
    for combo in combos:
        print(f"  - {combo.to_search_string()}")
    
    # Test expiring items
    expiring = grouper.get_expiring_items(days_threshold=3)
    print(f"\n✓ Expiring Items ({len(expiring)}):")
    for item in expiring:
        print(f"  - {item['name']}: {item['days_until_expiry']} days")
    
    # Test recipe validation
    from app.services.recipe_validator import RecipeValidator
    
    validator = RecipeValidator()
    mock_recipes = await MockRecipeCacheManager().find_cached_recipes([])
    
    valid, rejected = validator.validate_batch(mock_recipes)
    print(f"\n✓ Recipe Validation:")
    print(f"  Valid: {len(valid)}")
    print(f"  Rejected: {len(rejected)}")
    
    if rejected:
        print("\n  Rejection reasons:")
        for item in rejected:
            print(f"    - {item['recipe']['title']}: {item['rejection_reason']}")
    
    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
