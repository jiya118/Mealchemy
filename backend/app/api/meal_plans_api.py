"""
API endpoints for meal planning.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
import logging

from app.database.db import db_manager
from app.crud.mealplanCrud import get_meal_plan_crud, MealPlanCRUD
from app.crud.pantryItemCrud import get_pantry_item_crud, PantryItemCRUD
from app.schema.meal_plan import (
    MealPlanCreate,
    MealPlanResponse,
    MealPlanList,
    RegenerateMealRequest,
    CompleteMealRequest,
    MealPlanStatusEnum,
    MealPlanConfig,
    DayMeals,
    Meal
)
from app.schema.pantryItem import PantryItemResponse
from app.services.meal_plan_generator import MealPlanGenerator
from app.services.pantry_analyzer import PantryAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meal-plans", tags=["Meal Plans"])


async def get_meal_plan_crud_instance() -> MealPlanCRUD:
    """Dependency to get meal plan CRUD instance."""
    collection = db_manager.get_collection("meal_plans")
    return get_meal_plan_crud(collection)


async def get_pantry_crud_instance() -> PantryItemCRUD:
    """Dependency to get pantry CRUD instance."""
    collection = db_manager.get_collection("pantry_items")
    return get_pantry_item_crud(collection)


@router.post(
    "/generate",
    response_model=MealPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate weekly meal plan"
)
async def generate_meal_plan(
    config: MealPlanCreate,
    meal_plan_crud: MealPlanCRUD = Depends(get_meal_plan_crud_instance),
    pantry_crud: PantryItemCRUD = Depends(get_pantry_crud_instance)
):
    """
    Generate a complete weekly meal plan based on pantry inventory.
    
    - **meals_per_day**: 1, 2, or 3 meals per day
    - **diet_type**: standard, vegetarian, vegan, eggetarian
    - **servings**: Number of servings per recipe
    - **days**: Number of days to plan (default 7)
    
    The system will:
    1. Analyze current pantry inventory
    2. Prioritize items expiring soon
    3. Generate recipes matching available ingredients
    4. Create shopping list for missing items
    5. Provide helpful notes and warnings
    """
    logger.info(f"Generating meal plan with config: {config}")
    
    try:
        # Fetch all pantry items
        pantry_result = await pantry_crud.get_all(skip=0, limit=1000)
        pantry_items = pantry_result.items
        
        if not pantry_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pantry items found. Please add items to your pantry first."
            )
        
        logger.info(f"Found {len(pantry_items)} pantry items")
        
        # Create meal plan configuration
        plan_config = MealPlanConfig(
            meals_per_day=config.meals_per_day,
            diet_type=config.diet_type,
            servings=config.servings,
            days=config.days
        )
        
        # Generate meal plan
        generator = MealPlanGenerator(pantry_items)
        weekly_meals, shopping_list, expiry_warnings = await generator.generate_weekly_plan(plan_config)
        
        # Save to database
        saved_plan = await meal_plan_crud.create(
            weekly_meals=weekly_meals,
            shopping_list=[item.model_dump() for item in shopping_list],
            expiry_warnings=expiry_warnings,
            config=plan_config.model_dump()
        )
        
        logger.info(f"Meal plan created with ID: {saved_plan.id}")
        
        return saved_plan
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating meal plan: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate meal plan: {str(e)}"
        )


@router.get(
    "",
    response_model=MealPlanList,
    summary="Get all meal plans"
)
async def get_meal_plans(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    crud: MealPlanCRUD = Depends(get_meal_plan_crud_instance)
):
    """
    Get a paginated list of all meal plans.
    """
    skip = (page - 1) * page_size
    
    return await crud.get_all(
        skip=skip,
        limit=page_size,
        status=status_filter
    )


@router.get(
    "/active",
    response_model=MealPlanResponse,
    summary="Get active meal plan"
)
async def get_active_meal_plan(
    crud: MealPlanCRUD = Depends(get_meal_plan_crud_instance)
):
    """
    Get the currently active meal plan.
    """
    plan = await crud.get_active_plan()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active meal plan found"
        )
    
    return plan


@router.get(
    "/{plan_id}",
    response_model=MealPlanResponse,
    summary="Get meal plan by ID"
)
async def get_meal_plan(
    plan_id: str,
    crud: MealPlanCRUD = Depends(get_meal_plan_crud_instance)
):
    """
    Get a specific meal plan by its ID.
    """
    plan = await crud.get_by_id(plan_id)
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan with ID {plan_id} not found"
        )
    
    return plan


@router.post(
    "/{plan_id}/regenerate",
    response_model=MealPlanResponse,
    summary="Regenerate a single meal"
)
async def regenerate_meal(
    plan_id: str,
    request: RegenerateMealRequest,
    meal_plan_crud: MealPlanCRUD = Depends(get_meal_plan_crud_instance),
    pantry_crud: PantryItemCRUD = Depends(get_pantry_crud_instance)
):
    """
    Regenerate a single meal within the plan.
    
    This creates a new virtual pantry, subtracts all meals before the target meal,
    and generates a new recipe based on remaining ingredients.
    """
    logger.info(f"Regenerating {request.day.value} {request.meal_type.value} for plan {plan_id}")
    
    try:
        # Get the existing plan
        plan = await meal_plan_crud.get_by_id(plan_id)
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meal plan with ID {plan_id} not found"
            )
        
        # Get current pantry
        pantry_result = await pantry_crud.get_all(skip=0, limit=1000)
        pantry_items = pantry_result.items
        
        # Create virtual pantry
        analyzer = PantryAnalyzer(pantry_items)
        virtual_pantry = analyzer.create_virtual_pantry()
        
        # Deduct ingredients from all meals BEFORE the target meal
        day_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        target_day_index = day_order.index(request.day.value)
        
        for day_meals in plan.meals:
            day_index = day_order.index(day_meals.day.value)
            
            if day_index < target_day_index:
                # Deduct all meals from this day
                for meal in day_meals.meals:
                    analyzer.deduct_ingredients(meal.ingredients_used, plan.config.servings)
            elif day_index == target_day_index:
                # Deduct only meals before the target meal type
                meal_type_order = ["breakfast", "lunch", "dinner"]
                target_meal_index = meal_type_order.index(request.meal_type.value)
                
                for meal in day_meals.meals:
                    meal_index = meal_type_order.index(meal.meal_type.value)
                    if meal_index < target_meal_index:
                        analyzer.deduct_ingredients(meal.ingredients_used, plan.config.servings)
                break
        
        # Get expiring items
        expiring_items = analyzer.get_expiring_items(days=plan.config.days)
        
        # Generate new meal
        generator = MealPlanGenerator(pantry_items)
        generator.pantry_analyzer = analyzer  # Use our adjusted analyzer
        generator.config = plan.config
        
        new_meal, shopping_items = await generator._generate_single_meal(
            virtual_pantry=virtual_pantry,
            expiring_items=expiring_items,
            meal_type=request.meal_type,
            day_num=target_day_index
        )
        
        # Update the meal in the plan
        updated_plan = await meal_plan_crud.update_meal(
            plan_id=plan_id,
            day=request.day,
            meal_type=request.meal_type,
            new_meal=new_meal
        )
        
        if not updated_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to update meal in plan"
            )
        
        logger.info(f"Successfully regenerated meal")
        
        return updated_plan
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating meal: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate meal: {str(e)}"
        )


@router.patch(
    "/{plan_id}/complete",
    response_model=MealPlanResponse,
    summary="Mark meal as completed"
)
async def complete_meal(
    plan_id: str,
    request: CompleteMealRequest,
    meal_plan_crud: MealPlanCRUD = Depends(get_meal_plan_crud_instance),
    pantry_crud: PantryItemCRUD = Depends(get_pantry_crud_instance)
):
    """
    Mark a meal as completed and deduct ingredients from actual pantry.
    
    This is when the REAL pantry reduction happens!
    """
    logger.info(f"Completing {request.day.value} {request.meal_type.value} for plan {plan_id}")
    
    try:
        # Get the meal plan
        plan = await meal_plan_crud.get_by_id(plan_id)
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meal plan with ID {plan_id} not found"
            )
        
        # Find the specific meal
        target_meal = None
        for day_meals in plan.meals:
            if day_meals.day == request.day:
                for meal in day_meals.meals:
                    if meal.meal_type == request.meal_type:
                        target_meal = meal
                        break
                break
        
        if not target_meal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meal not found in plan"
            )
        
        if target_meal.is_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Meal is already completed"
            )
        
        # Deduct ingredients from REAL pantry
        for ingredient in target_meal.ingredients_used:
            if ingredient.from_pantry and ingredient.pantry_item_id:
                try:
                    # Calculate quantity to deduct based on servings
                    quantity_delta = -1 * (ingredient.quantity * plan.config.servings)
                    
                    # Update pantry item
                    await pantry_crud.update_quantity(
                        item_id=ingredient.pantry_item_id,
                        quantity_delta=quantity_delta
                    )
                    
                    logger.debug(f"Deducted {abs(quantity_delta)} {ingredient.unit} of {ingredient.name}")
                    
                except Exception as e:
                    logger.warning(f"Failed to deduct {ingredient.name}: {str(e)}")
        
        # Mark meal as completed
        updated_plan = await meal_plan_crud.complete_meal(
            plan_id=plan_id,
            day=request.day,
            meal_type=request.meal_type
        )
        
        if not updated_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to mark meal as completed"
            )
        
        logger.info(f"Meal completed and pantry updated")
        
        return updated_plan
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing meal: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete meal: {str(e)}"
        )


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete meal plan"
)
async def delete_meal_plan(
    plan_id: str,
    crud: MealPlanCRUD = Depends(get_meal_plan_crud_instance)
):
    """
    Delete a meal plan by its ID.
    """
    deleted = await crud.delete(plan_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan with ID {plan_id} not found"
        )
    
    return None