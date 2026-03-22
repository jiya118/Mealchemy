#!/usr/bin/env python3
"""
Quick Test Script for Single-Shot Meal Planner Integration

Run this to verify the integration works before deploying.
"""
import sys
import os
from datetime import datetime, timedelta
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock data for testing
MOCK_PANTRY = [
    {
        'name': 'chicken breast',
        'quantity': 500,
        'unit': 'g',
        'category': 'protein',
        'expiry_date': (datetime.now() + timedelta(days=2)).isoformat()
    },
    {
        'name': 'tomatoes',
        'quantity': 5,
        'unit': 'pieces',
        'category': 'vegetable',
        'expiry_date': (datetime.now() + timedelta(days=4)).isoformat()
    },
    {
        'name': 'onions',
        'quantity': 3,
        'unit': 'pieces',
        'category': 'vegetable',
        'expiry_date': (datetime.now() + timedelta(days=10)).isoformat()
    },
    {
        'name': 'garlic',
        'quantity': 1,
        'unit': 'bulb',
        'category': 'vegetable',
        'expiry_date': (datetime.now() + timedelta(days=14)).isoformat()
    },
    {
        'name': 'rice',
        'quantity': 1,
        'unit': 'kg',
        'category': 'grain',
        'expiry_date': None
    },
    {
        'name': 'pasta',
        'quantity': 500,
        'unit': 'g',
        'category': 'grain',
        'expiry_date': None
    },
]


class MockPantryItem:
    """Mock Pydantic model for testing."""
    def __init__(self, data: Dict):
        self.name = data['name']
        self.quantity = data['quantity']
        self.unit = data['unit']
        self.category = data['category']
        self.expiry_date = data['expiry_date']


class MockRecipeCRUD:
    """Mock recipe CRUD for testing."""
    pass


def test_imports():
    """Test 1: Verify all imports work."""
    print("\n" + "="*60)
    print("TEST 1: Checking Imports")
    print("="*60)
    
    try:
        from app.services.smart_ingredient_grouper import SmartIngredientGrouper
        print("✓ SmartIngredientGrouper imported")
        
        from app.services.recipe_validator import RecipeValidator
        print("✓ RecipeValidator imported")
        
        from app.services.recipe_scorer import RecipeScorer
        print("✓ RecipeScorer imported")
        
        from app.services.virtual_pantry_manager import VirtualPantryManager
        print("✓ VirtualPantryManager imported")
        
        from app.services.single_shot_meal_planner import SingleShotMealPlanGenerator
        print("✓ SingleShotMealPlanGenerator imported")
        
        print("\n✅ All imports successful!")
        return True
    
    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        print("\nFix: Ensure files are in app/services/ and __init__.py exists")
        return False


def test_pantry_conversion():
    """Test 2: Verify Pydantic to dict conversion."""
    print("\n" + "="*60)
    print("TEST 2: Pantry Data Conversion")
    print("="*60)
    
    try:
        from app.services.single_shot_meal_planner import SingleShotMealPlanGenerator
        
        # Create mock Pydantic objects
        mock_items = [MockPantryItem(item) for item in MOCK_PANTRY]
        
        # Test conversion (without full initialization)
        generator = SingleShotMealPlanGenerator.__new__(SingleShotMealPlanGenerator)
        converted = generator._convert_pydantic_to_dict(mock_items)
        
        print(f"✓ Converted {len(converted)} pantry items")
        print(f"  Sample: {converted[0]['name']} ({converted[0]['quantity']}{converted[0]['unit']})")
        
        print("\n✅ Conversion successful!")
        return True
    
    except Exception as e:
        print(f"\n❌ Conversion failed: {e}")
        return False


def test_ingredient_grouper():
    """Test 3: Verify ingredient grouping logic."""
    print("\n" + "="*60)
    print("TEST 3: Smart Ingredient Grouping")
    print("="*60)
    
    try:
        from app.services.smart_ingredient_grouper import SmartIngredientGrouper
        
        grouper = SmartIngredientGrouper(MOCK_PANTRY)
        
        # Test categorization
        proteins = grouper.categorized['proteins']
        vegetables = grouper.categorized['vegetables']
        grains = grouper.categorized['grains']
        
        print(f"✓ Proteins: {[p['name'] for p in proteins]}")
        print(f"✓ Vegetables: {[v['name'] for v in vegetables]}")
        print(f"✓ Grains: {[g['name'] for g in grains]}")
        
        # Test combinations
        combos = grouper.create_smart_combinations(max_combos=3)
        print(f"\n✓ Created {len(combos)} combinations:")
        for combo in combos:
            print(f"  - {combo.to_search_string()}")
        
        # Test expiring items
        expiring = grouper.get_expiring_items(days_threshold=7)
        print(f"\n✓ Items expiring in 7 days: {[e['name'] for e in expiring]}")
        
        print("\n✅ Grouping logic works!")
        return True
    
    except Exception as e:
        print(f"\n❌ Grouping failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_recipe_validator():
    """Test 4: Verify recipe validation."""
    print("\n" + "="*60)
    print("TEST 4: Recipe Validation")
    print("="*60)
    
    try:
        from app.services.recipe_validator import RecipeValidator
        
        validator = RecipeValidator(min_ingredients=5, min_cook_time=10)
        
        # Test recipes
        good_recipe = {
            'id': 1,
            'title': 'Chicken Curry',
            'readyInMinutes': 30,
            'extendedIngredients': [
                {'name': 'chicken'}, {'name': 'curry powder'}, 
                {'name': 'onion'}, {'name': 'tomato'},
                {'name': 'rice'}, {'name': 'garlic'}
            ]
        }
        
        bad_recipe = {
            'id': 2,
            'title': 'Berry Smoothie',
            'readyInMinutes': 5,
            'extendedIngredients': [
                {'name': 'berries'}, {'name': 'milk'}
            ]
        }
        
        is_valid, reason = validator.validate_recipe(good_recipe)
        print(f"✓ Good recipe valid: {is_valid} (reason: {reason or 'passed'})")
        
        is_valid, reason = validator.validate_recipe(bad_recipe)
        print(f"✓ Bad recipe rejected: {not is_valid} (reason: {reason})")
        
        # Batch validation
        validated, rejected = validator.validate_batch([good_recipe, bad_recipe])
        print(f"\n✓ Batch: {len(validated)} passed, {len(rejected)} rejected")
        
        print("\n✅ Validation logic works!")
        return True
    
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_virtual_pantry():
    """Test 5: Verify virtual pantry management."""
    print("\n" + "="*60)
    print("TEST 5: Virtual Pantry Management")
    print("="*60)
    
    try:
        from app.services.virtual_pantry_manager import VirtualPantryManager
        
        manager = VirtualPantryManager(MOCK_PANTRY)
        
        print(f"✓ Initialized with {len(manager.virtual_pantry)} items")
        
        # Test recipe check
        test_recipe = {
            'extendedIngredients': [
                {'name': 'chicken breast', 'amount': 200, 'unit': 'g'},
                {'name': 'rice', 'amount': 100, 'unit': 'g'},
                {'name': 'onions', 'amount': 1, 'unit': 'piece'}
            ]
        }
        
        can_make, missing = manager.can_make_recipe(test_recipe)
        print(f"✓ Can make recipe: {can_make}")
        if not can_make:
            print(f"  Missing: {missing}")
        
        # Test deduction
        if can_make:
            deducted = manager.deduct_ingredients(test_recipe, "monday")
            print(f"✓ Deducted {len(deducted)} ingredients")
            print(f"  History: {len(manager.deduction_history)} entries")
        
        # Test clone
        clone = manager.clone()
        print(f"✓ Cloned pantry: {len(clone.virtual_pantry)} items")
        
        print("\n✅ Pantry management works!")
        return True
    
    except Exception as e:
        print(f"\n❌ Pantry management failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("SINGLE-SHOT MEAL PLANNER INTEGRATION TEST")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Pantry Conversion", test_pantry_conversion()))
    results.append(("Ingredient Grouper", test_ingredient_grouper()))
    results.append(("Recipe Validator", test_recipe_validator()))
    results.append(("Virtual Pantry", test_virtual_pantry()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Ready to integrate.")
        print("\nNext steps:")
        print("1. Copy files to app/services/")
        print("2. Update meal_plan.py endpoint")
        print("3. Set USE_NEW_GENERATOR=false in .env")
        print("4. Test with real FastAPI server")
        return 0
    else:
        print("\n⚠️  Some tests failed. Fix issues before proceeding.")
        return 1


if __name__ == '__main__':
    sys.exit(main())