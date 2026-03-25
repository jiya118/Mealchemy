"""
Single-Shot Meal Plan Generator - FastAPI Integration Version

Adapted to work with existing FastAPI structure and Pydantic models.
"""
from typing import List, Dict, Any, Optional, Tuple
import json
import logging
import random

from app.services.smart_ingredient_grouper import SmartIngredientGrouper
from app.services.recipe_validator import RecipeValidator
from app.services.recipe_scorer import RecipeScorer
from app.services.virtual_pantry_manager import VirtualPantryManager
from app.services.recipe_cache_manager import RecipeCacheManager
from app.services.spoonacular_client import spoonacular_client
from app.services.llm_client import llm_client
from app.schema.pantryItem import PantryItemResponse
from app.crud.recipe import RecipeCRUD

logger = logging.getLogger(__name__)


class SingleShotMealPlanGenerator:
    """
    Generates meal plans using pre-validated recipes and a single LLM call.
    
    Integrated with FastAPI project structure.
    """
    
    DAYS_OF_WEEK = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    def __init__(
        self,
        pantry_items: List[PantryItemResponse],
        recipe_crud: RecipeCRUD
    ):
        """
        Initialize generator with FastAPI dependencies.
        
        Args:
            pantry_items: List of PantryItemResponse from database
            recipe_crud: RecipeCRUD instance for cache access
        """
        # Convert Pydantic models to dict format for internal processing
        self.pantry_items = self._convert_pydantic_to_dict(pantry_items)
        
        # Initialize services
        self.recipe_crud = recipe_crud
        self.cache_manager = RecipeCacheManager(recipe_crud)
        self.spoonacular_client = spoonacular_client
        self.llm_client = llm_client
        
        # Initialize new components
        self.ingredient_grouper = SmartIngredientGrouper(self.pantry_items)
        self.recipe_validator = RecipeValidator(min_ingredients=5, min_cook_time=10)
        self.virtual_pantry = VirtualPantryManager(self.pantry_items)
    
    def _convert_pydantic_to_dict(
        self, 
        pantry_items: List[PantryItemResponse]
    ) -> List[Dict[str, Any]]:
        """Convert Pydantic models to dict format."""
        converted = []
        
        for item in pantry_items:
            # Handle expiry_date - could be datetime, date, or string
            expiry_str = None
            if item.expiry_date:
                if hasattr(item.expiry_date, 'isoformat'):
                    expiry_str = item.expiry_date.isoformat()
                else:
                    expiry_str = str(item.expiry_date)
            
            converted.append({
                'name': item.name,
                'quantity': float(item.quantity) if item.quantity else 0.0,
                'unit': item.unit if item.unit else '',
                'category': item.category if item.category else 'other',
                'expiry_date': expiry_str
            })
        
        return converted
    
    async def generate_meal_plan(
        self,
        days: int = 7,
        diet_type: str = 'standard',
        servings: int = 2,
        meals_per_day: int = 2
    ) -> Dict[str, Any]:
        """
        Generate complete meal plan.
        
        Args:
            days: Number of days to plan
            diet_type: Diet restriction ('standard', 'vegetarian', 'vegan', etc.)
            servings: Number of servings per meal
            meals_per_day: Number of meals per day (1, 2, or 3)
            
        Returns:
            Complete meal plan dict with success/error status
        """
        logger.info(f"=== Starting Single-Shot Meal Plan Generation ({days} days, {meals_per_day} meals/day) ===")
        
        try:
            total_meals_needed = days * meals_per_day
            
            # PHASE 1: Pre-filter recipes (No LLM)
            logger.info("PHASE 1: Pre-filtering recipes...")
            validated_recipes = await self._prefetch_and_validate_recipes(diet_type)
            
            if len(validated_recipes) < total_meals_needed:
                logger.warning(f"Only {len(validated_recipes)} recipes for {total_meals_needed} meal slots, will reuse some")
                # Don't fail - we'll reuse recipes if needed
            
            logger.info(f"✓ {len(validated_recipes)} validated recipes ready")
            
            # PHASE 2: Score and rank recipes (No LLM)
            logger.info("PHASE 2: Scoring recipes by expiry urgency...")
            expiring_items = self.ingredient_grouper.get_expiring_items(days_threshold=days)
            
            scorer = RecipeScorer(
                virtual_pantry=self.virtual_pantry.virtual_pantry,
                expiring_items=expiring_items
            )
            
            scored_recipes = scorer.score_and_rank_recipes(validated_recipes, day_number=0)
            
            if scored_recipes:
                logger.info(f"✓ Recipes scored (top score: {scored_recipes[0]['score']:.1f})")
            else:
                logger.warning("No scored recipes available")
                return {
                    'success': False,
                    'error': 'No recipes could be scored',
                    'suggestion': 'Add more pantry items or broaden diet restrictions'
                }
            
            # Shuffle recipes with similar scores to add variety
            scored_recipes = self._shuffle_similar_scores(scored_recipes)
            
            # PHASE 3: Single LLM call (MINIMAL TOKENS)
            logger.info("PHASE 3: Calling LLM for meal planning...")
            llm_plan = await self._call_llm_for_planning(
                scored_recipes=scored_recipes[:25],
                days=days,
                meals_per_day=meals_per_day,
                expiring_items=expiring_items
            )
            
            if not llm_plan:
                logger.warning("LLM planning failed, using algorithmic fallback")
                return await self._algorithmic_fallback(scored_recipes, days, servings, meals_per_day)
            
            logger.info(f"✓ LLM plan received")
            
            # PHASE 4: Validate and build final plan (No LLM)
            logger.info("PHASE 4: Validating and building final plan...")
            final_plan = await self._build_validated_plan(
                llm_plan=llm_plan,
                scored_recipes=scored_recipes,
                days=days,
                servings=servings,
                meals_per_day=meals_per_day
            )
            
            logger.info("=== Meal Plan Generation Complete ===")
            
            return final_plan
            
        except Exception as e:
            logger.error(f"Meal plan generation failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'Generation failed: {str(e)}',
                'suggestion': 'Please try again or contact support'
            }
    
    async def _prefetch_and_validate_recipes(
        self,
        diet_type: str
    ) -> List[Dict[str, Any]]:
        """Phase 1: Get and validate recipes."""
        all_recipes = []
        
        # Step 1: Create smart ingredient combinations
        combos = self.ingredient_grouper.create_smart_combinations(max_combos=5)
        logger.info(f"Created {len(combos)} smart ingredient combinations")
        
        # CRITICAL FIX: Filter out non-compliant proteins BEFORE searching
        if diet_type == 'vegan':
            # Remove paneer, eggs from search combos
            vegan_combos = []
            for combo in combos:
                # Skip if combo contains non-vegan proteins
                combo_str = combo.to_search_string().lower()
                if any(bad in combo_str for bad in ['paneer', 'egg', 'cheese', 'milk', 'curd']):
                    logger.info(f"Skipping non-vegan combo: {combo.to_search_string()}")
                    continue
                vegan_combos.append(combo)
            combos = vegan_combos
            logger.info(f"After vegan filter: {len(combos)} combos remain")
        
        if diet_type == 'vegetarian':
            # Remove meat/fish from search combos
            veg_combos = []
            for combo in combos:
                combo_str = combo.to_search_string().lower()
                if any(bad in combo_str for bad in ['chicken', 'beef', 'pork', 'fish', 'meat']):
                    logger.info(f"Skipping non-vegetarian combo: {combo.to_search_string()}")
                    continue
                veg_combos.append(combo)
            combos = veg_combos
            logger.info(f"After vegetarian filter: {len(combos)} combos remain")
        
        # If no valid combos after filtering, create generic vegan/vegetarian ones
        if len(combos) == 0:
            logger.warning(f"No valid combos for {diet_type}, creating generic ones...")
            combos = self._create_diet_specific_combos(diet_type)
        
        # Step 2: Search cache for each combo
        for combo in combos:
            combo_ingredients = combo.to_search_string().split(',')
            logger.info(f"Searching cache with: {', '.join(combo_ingredients)} (diet: {diet_type})")
            
            # Pass diet type correctly - cache manager needs to filter
            cached = await self.cache_manager.find_cached_recipes(
                pantry_ingredients=combo_ingredients,
                diet_type=diet_type if diet_type != 'standard' else None,
                min_recipes=5
            )
            
            for recipe_model in cached:
                if hasattr(recipe_model, 'full_recipe') and recipe_model.full_recipe:
                    all_recipes.append(recipe_model.full_recipe)
                elif hasattr(recipe_model, 'model_dump'):
                    all_recipes.append(recipe_model.model_dump())
                elif hasattr(recipe_model, 'dict'):
                    all_recipes.append(recipe_model.dict())
                elif isinstance(recipe_model, dict):
                    all_recipes.append(recipe_model)
                else:
                    all_recipes.append(vars(recipe_model))
            logger.info(f"  Cache hits: {len(cached)}")
        
        # Step 3: Deduplicate
        unique_recipes = self._deduplicate_recipes(all_recipes)
        
        # Step 4: If not enough from cache, call Spoonacular
        if len(unique_recipes) < 20:
            logger.info(f"Cache insufficient ({len(unique_recipes)} recipes), calling Spoonacular...")
            
            best_combo = combos[0] if combos else None
            if best_combo:
                spoon_recipes = await self._fetch_from_spoonacular(
                    best_combo.to_search_string(),
                    diet_type=diet_type,
                    count=10
                )
                unique_recipes.extend(spoon_recipes)
                logger.info(f"  Spoonacular results: {len(spoon_recipes)}")
        
        # Step 5: Validate all recipes (including diet type check)
        validated, rejected = self.recipe_validator.validate_batch(
            unique_recipes,
            diet_type=diet_type  # Pass diet type for validation
        )
        
        if rejected:
            logger.info(f"\n{self.recipe_validator.get_validation_summary(rejected)}")
        
        return validated
    
    def _create_diet_specific_combos(self, diet_type: str) -> List:
        """Create generic ingredient combinations for specific diets."""
        from app.services.smart_ingredient_grouper import IngredientCombo
        
        combos = []
        
        if diet_type == 'vegan':
            # Use only vegan proteins
            vegan_proteins = []
            for item in self.pantry_items:
                name_lower = item['name'].lower()
                if any(v in name_lower for v in ['dal', 'lentil', 'chickpea', 'bean', 'tofu']):
                    vegan_proteins.append(item)
            
            # Get vegetables
            vegetables = self.ingredient_grouper.vegetables[:3]
            
            # Create combos with vegan proteins
            for protein in vegan_proteins[:2]:
                combo = IngredientCombo([protein] + vegetables)
                combos.append(combo)
            
            # If still no combos, use just vegetables
            if len(combos) == 0 and len(vegetables) >= 2:
                combos.append(IngredientCombo(vegetables[:3]))
        
        elif diet_type == 'vegetarian':
            # Can use paneer, eggs, dal
            veg_proteins = []
            for item in self.pantry_items:
                name_lower = item['name'].lower()
                if any(v in name_lower for v in ['paneer', 'egg', 'dal', 'lentil', 'chickpea', 'tofu']):
                    veg_proteins.append(item)
            
            vegetables = self.ingredient_grouper.vegetables[:3]
            
            for protein in veg_proteins[:3]:
                combo = IngredientCombo([protein] + vegetables)
                combos.append(combo)
        
        logger.info(f"Created {len(combos)} diet-specific combos")
        return combos
    
    async def _fetch_from_spoonacular(
        self,
        ingredients_str: str,
        diet_type: str,
        count: int
    ) -> List[Dict[str, Any]]:
        """Fetch recipes from Spoonacular API."""
        try:
            # Map diet type
            spoon_diet = None if diet_type == 'standard' else diet_type
            if diet_type == 'eggetarian':
                spoon_diet = 'vegetarian'
            
            # Search
            results = self.spoonacular_client.search_recipes_by_ingredients(
                ingredients=ingredients_str,
                number=count,
                ranking=1,
                diet=spoon_diet
            )
            
            # Get full details and cache
            full_recipes = []
            for result in results:
                full_recipe = self.spoonacular_client.get_recipe_details(result['id'])
                
                # Cache it
                cached = await self.cache_manager.cache_spoonacular_recipe(
                    full_recipe,
                    diet_type=diet_type
                )
                
                await self.recipe_crud.create(cached)
                full_recipes.append(full_recipe)
            
            return full_recipes
            
        except Exception as e:
            logger.error(f"Spoonacular fetch failed: {e}")
            return []
    
    def _deduplicate_recipes(self, recipes: List[Dict]) -> List[Dict]:
        """Remove duplicate recipes by ID."""
        seen_ids = set()
        unique = []
        
        for recipe in recipes:
            recipe_id = recipe.get('id') or recipe.get('recipe_id')
            if recipe_id and recipe_id not in seen_ids:
                seen_ids.add(recipe_id)
                unique.append(recipe)
        
        return unique
    
    def _shuffle_similar_scores(self, scored_recipes: List[Dict]) -> List[Dict]:
        """Shuffle recipes that have similar scores to add variety between runs."""
        if not scored_recipes:
            return scored_recipes
        
        # Group recipes by score buckets (within 5 points of each other)
        result = []
        current_bucket = [scored_recipes[0]]
        
        for recipe in scored_recipes[1:]:
            if abs(recipe['score'] - current_bucket[0]['score']) <= 5:
                current_bucket.append(recipe)
            else:
                random.shuffle(current_bucket)
                result.extend(current_bucket)
                current_bucket = [recipe]
        
        random.shuffle(current_bucket)
        result.extend(current_bucket)
        
        return result
    
    async def _call_llm_for_planning(
        self,
        scored_recipes: List[Dict],
        days: int,
        meals_per_day: int,
        expiring_items: List[Dict]
    ) -> Optional[Dict]:
        """Phase 3: Single LLM call for meal planning."""
        prompt = self._build_llm_prompt(scored_recipes, days, meals_per_day, expiring_items)
        
        logger.info(f"Prompt size: ~{len(prompt)} characters")
        
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a meal planning assistant. Respond ONLY with valid JSON, no markdown."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # Use higher temperature for variety between runs
            response = self.llm_client._make_request(messages, temperature=0.7)
            
            if not response:
                return None
            
            # Parse JSON
            response_text = response.strip()
            
            # Remove markdown if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            plan = json.loads(response_text.strip())
            logger.info(f"LLM returned plan for days: {list(plan.keys())}")
            return plan
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}\nResponse: {response_text[:200]}")
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
    
    def _build_llm_prompt(
        self,
        recipes: List[Dict],
        days: int,
        meals_per_day: int,
        expiring_items: List[Dict]
    ) -> str:
        """Build compact LLM prompt."""
        pantry_formatted = self.virtual_pantry.format_for_llm(include_staples=False)
        pantry_str = json.dumps(pantry_formatted[:30], indent=1)
        
        expiring_str = ", ".join([
            f"{item['name']} ({item['days_until_expiry']}d)"
            for item in expiring_items[:10]
        ]) if expiring_items else "None"
        
        # Format recipes
        recipes_formatted = []
        for i, recipe in enumerate(recipes[:20], 1):
            main_ings = []
            ingredients = recipe.get('extendedIngredients', 
                                    recipe.get('ingredients_summary', []))
            
            for ing in ingredients[:5]:
                if isinstance(ing, dict):
                    name = ing.get('name', ing.get('nameClean', ''))
                else:
                    name = getattr(ing, 'name', str(ing))
                
                if name and not any(staple in name.lower() 
                                   for staple in ['salt', 'pepper', 'oil', 'water']):
                    main_ings.append(name)
            
            uses_expiring = any(
                item['name'].lower() in recipe.get('title', recipe.get('name', '')).lower()
                or any(item['name'].lower() in ing.lower() for ing in main_ings)
                for item in expiring_items
            )
            
            cook_time = recipe.get('readyInMinutes', recipe.get('ready_in_minutes', '?'))
            score = recipe.get('score', 0)
            
            recipe_str = {
                'id': i,
                'name': recipe.get('title', recipe.get('name')),
                'time': f"{cook_time}min",
                'score': f"{score:.0f}",
                'needs': main_ings[:4]
            }
            
            if uses_expiring:
                recipe_str['\u26a0\ufe0f'] = 'EXPIRING'
            
            recipes_formatted.append(recipe_str)
        
        recipes_str = json.dumps(recipes_formatted, indent=1)
        
        # Build meal type labels
        meal_type_labels = ['dinner']
        if meals_per_day >= 2:
            meal_type_labels = ['lunch', 'dinner']
        if meals_per_day >= 3:
            meal_type_labels = ['breakfast', 'lunch', 'dinner']
        
        meal_types_str = ', '.join(meal_type_labels)
        
        # Build example JSON based on meals_per_day
        if meals_per_day == 1:
            example_json = '{\n  "monday": {"recipe_id": 1, "reason": "Uses expiring spinach"},\n  "tuesday": {"recipe_id": 5, "reason": "Different protein (eggs)"},\n  ...\n}'
        else:
            example_json = '{\n  "monday": [\n    {"recipe_id": 1, "meal_type": "lunch", "reason": "Uses expiring spinach"},\n    {"recipe_id": 3, "meal_type": "dinner", "reason": "Different protein"}\n  ],\n  "tuesday": [\n    {"recipe_id": 5, "meal_type": "lunch", "reason": "Quick dal"},\n    {"recipe_id": 7, "meal_type": "dinner", "reason": "Uses tomatoes"}\n  ],\n  ...\n}'

        prompt = f"""Plan {days} days of meals ({meals_per_day} meal(s) per day: {meal_types_str}) with MAXIMUM VARIETY.

PANTRY:
{pantry_str}

EXPIRING SOON: {expiring_str}

RECIPES (sorted by score):
{recipes_str}

CRITICAL RULES:
1. \u26a0\ufe0f NEVER repeat the same recipe or similar recipes (e.g., "Palak Paneer" and "Luscious Palak Paneer" are TOO SIMILAR)
2. \u26a0\ufe0f Use DIFFERENT main ingredients each day (if Monday uses paneer, Tuesday should use eggs/dal/etc.)
3. Each recipe_id MUST be unique across the ENTIRE plan - never use the same ID twice
4. Use recipes marked \u26a0\ufe0f EXPIRING in first 2-3 days
5. Prefer higher-score recipes
6. Don't repeat main protein within 2 days
7. Quick recipes (\u226430min) for weekdays (Mon-Fri)

VARIETY CHECK:
- Each meal should feel like a COMPLETELY DIFFERENT dish
- Mix proteins: rotate between paneer, eggs, lentils, chickpeas, etc.
- Mix vegetables: spinach one day, tomato-based another, potato-based, etc.

You MUST assign exactly {meals_per_day} recipe(s) per day for ALL {days} days.

Respond with JSON ONLY (no markdown):
{example_json}

Days: {', '.join(self.DAYS_OF_WEEK[:days])}"""

        return prompt
    
    async def _build_validated_plan(
        self,
        llm_plan: Dict,
        scored_recipes: List[Dict],
        days: int,
        servings: int,
        meals_per_day: int = 1
    ) -> Dict[str, Any]:
        """Phase 4: Validate LLM's choices and build final plan."""
        recipe_map = {i+1: recipe for i, recipe in enumerate(scored_recipes[:20])}
        
        daily_meals = []
        pantry = self.virtual_pantry.clone()
        
        for day_num in range(days):
            day_name = self.DAYS_OF_WEEK[day_num]
            
            day_plan = llm_plan.get(day_name, {})
            
            # Handle both single-meal and multi-meal formats
            if isinstance(day_plan, list):
                # Multi-meal format: [{recipe_id: 1, ...}, {recipe_id: 2, ...}]
                meal_entries = day_plan
            elif isinstance(day_plan, dict) and 'recipe_id' in day_plan:
                # Single-meal format: {recipe_id: 1, ...}
                meal_entries = [day_plan]
            else:
                meal_entries = []
            
            # Ensure we have enough meals for this day
            while len(meal_entries) < meals_per_day:
                meal_entries.append({'recipe_id': None, 'reason': 'Auto-filled'})
            
            for meal_entry in meal_entries[:meals_per_day]:
                recipe_id = meal_entry.get('recipe_id') if isinstance(meal_entry, dict) else None
                
                if not recipe_id or recipe_id not in recipe_map:
                    logger.warning(f"{day_name}: Invalid recipe_id {recipe_id}, using fallback")
                    recipe = await self._pick_fallback_recipe(pantry, scored_recipes, daily_meals)
                else:
                    # Use the LLM's chosen recipe directly - missing ingredients go to shopping list
                    recipe = recipe_map[recipe_id]
                    can_make, missing = pantry.can_make_recipe(recipe)
                    if missing:
                        logger.info(f"{day_name}: {recipe.get('title')} missing {len(missing)} ingredients (will add to shopping list)")
                
                # Deduct whatever ingredients are available from pantry
                deducted = pantry.deduct_ingredients(recipe, day_name)
                
                reason = meal_entry.get('reason', 'Automatically selected') if isinstance(meal_entry, dict) else 'Automatically selected'
                
                meal = {
                    'day': day_name,
                    'recipe_id': recipe.get('id', recipe.get('recipe_id')),
                    'recipe_name': recipe.get('title', recipe.get('name')),
                    'ready_in_minutes': recipe.get('readyInMinutes', recipe.get('ready_in_minutes')),
                    'servings': servings,
                    'reason': reason,
                    'score': recipe.get('score', 0),
                    'ingredients_from_pantry': [d['name'] for d in deducted],
                    'full_recipe': recipe
                }
                
                daily_meals.append(meal)
        
        shopping_list = self._generate_shopping_list(daily_meals, scored_recipes)
        
        return {
            'success': True,
            'meals': daily_meals,
            'shopping_list': shopping_list,
            'pantry_summary': {
                'items_used': len(pantry.get_depleted_items()),
                'items_remaining': len(pantry.get_items_with_stock())
            },
            'deduction_history': pantry.deduction_history
        }
    
    async def _pick_fallback_recipe(
        self,
        pantry: VirtualPantryManager,
        all_recipes: List[Dict],
        already_used: List[Dict]
    ) -> Dict:
        """Pick next best unused recipe. Missing ingredients go to shopping list."""
        used_ids = {meal['recipe_id'] for meal in already_used}
        used_names = {meal.get('recipe_name', '').lower() for meal in already_used if meal.get('recipe_name')}
        
        # First pass: find unused recipe that isn't similar to already-used ones
        for recipe in all_recipes:
            recipe_id = recipe.get('id', recipe.get('recipe_id'))
            recipe_name = recipe.get('title', recipe.get('name', '')).lower()
            
            if recipe_id in used_ids:
                continue
            
            # Skip if very similar name
            if any(used_name in recipe_name or recipe_name in used_name 
                   for used_name in used_names if used_name):
                continue
            
            logger.info(f"Fallback selected: {recipe.get('title', recipe.get('name'))}")
            return recipe
        
        # Second pass: any unused recipe (even with similar name)
        for recipe in all_recipes:
            recipe_id = recipe.get('id', recipe.get('recipe_id'))
            if recipe_id not in used_ids:
                logger.warning(f"Fallback (similar name allowed): {recipe.get('title', recipe.get('name'))}")
                return recipe
        
        # Absolute last resort: reuse first recipe
        if all_recipes:
            logger.error("All recipes exhausted, reusing first available")
            return all_recipes[0]
        
        return {}
    
    def _generate_shopping_list(
        self,
        daily_meals: List[Dict],
        all_recipes: List[Dict]
    ) -> List[Dict]:
        """Generate shopping list from meals."""
        shopping_map = {}
        
        for meal in daily_meals:
            recipe = meal.get('full_recipe', {})
            ingredients_from_pantry = set(meal.get('ingredients_from_pantry', []))
            
            ingredients = recipe.get('extendedIngredients', 
                                    recipe.get('ingredients_summary', []))
            
            for ing in ingredients:
                if isinstance(ing, dict):
                    name = ing.get('name', ing.get('nameClean', ''))
                    qty = ing.get('amount', 0)
                    unit = ing.get('unit', '')
                else:
                    name = getattr(ing, 'name', '')
                    qty = getattr(ing, 'quantity', 0)
                    unit = getattr(ing, 'unit', '')
                
                if not name or name.lower() in [n.lower() for n in ingredients_from_pantry]:
                    continue
                
                key = name.lower()
                if key in shopping_map:
                    shopping_map[key]['quantity'] += qty
                    shopping_map[key]['needed_for'].append(meal['recipe_name'])
                else:
                    shopping_map[key] = {
                        'name': name,
                        'quantity': qty,
                        'unit': unit,
                        'needed_for': [meal['recipe_name']]
                    }
        
        return list(shopping_map.values())
    async def _algorithmic_fallback(
        self,
        scored_recipes: List[Dict],
        days: int,
        servings: int,
        meals_per_day: int = 1
    ) -> Dict[str, Any]:
        """Simple algorithmic fallback if LLM fails. Assigns recipes round-robin."""
        logger.info("Using algorithmic fallback")
        
        daily_meals = []
        pantry = self.virtual_pantry.clone()
        recipe_index = 0
        total_recipes = len(scored_recipes)
        
        for day_num in range(days):
            day_name = self.DAYS_OF_WEEK[day_num]
            
            for meal_slot in range(meals_per_day):
                if total_recipes == 0:
                    break
                
                # Pick next recipe (round-robin through scored recipes)
                recipe = scored_recipes[recipe_index % total_recipes]
                recipe_index += 1
                
                deducted = pantry.deduct_ingredients(recipe, day_name)
                
                daily_meals.append({
                    'day': day_name,
                    'recipe_id': recipe.get('id', recipe.get('recipe_id')),
                    'recipe_name': recipe.get('title', recipe.get('name')),
                    'ready_in_minutes': recipe.get('readyInMinutes', recipe.get('ready_in_minutes')),
                    'servings': servings,
                    'reason': 'Algorithmic selection (LLM unavailable)',
                    'score': recipe.get('score', 0),
                    'ingredients_from_pantry': [d['name'] for d in deducted],
                    'full_recipe': recipe
                })
        
        return {
            'success': True,
            'meals': daily_meals,
            'shopping_list': self._generate_shopping_list(daily_meals, scored_recipes),
            'pantry_summary': {
                'items_used': len(pantry.get_depleted_items()),
                'items_remaining': len(pantry.get_items_with_stock())
            },
            'note': 'Generated using algorithmic fallback'
        }
