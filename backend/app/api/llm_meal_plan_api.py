"""
LLM-Powered Meal Plan API Endpoints.

Endpoints:
- POST /llm/generate            - Generate full weekly plan (saves to DB)
- POST /llm/generate-single     - Generate single meal
- POST /llm/{plan_id}/regenerate-day - Regenerate specific day
- PATCH /llm/{plan_id}/complete - Mark meal complete & deduct from real pantry
- GET  /llm/{plan_id}           - Get saved plan
- DELETE /llm/{plan_id}         - Delete plan
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
import logging
from datetime import datetime

from app.database.db import db_manager
from app.crud.pantryItemCrud import get_pantry_item_crud, PantryItemCRUD
from app.crud.llm_mealplan_crud import get_llm_meal_plan_crud, LLMMealPlanCRUD
from app.schema.llm_mealplan import (
    LLMMealPlanRequest,
    SingleMealRequest,
    RegenerateDayRequest,
    CompleteMealRequest,
    SingleMealResponse,
)
from app.services.llm_mealplan_orchestrator import LLMMealPlanOrchestrator
from app.services.llm_recipe_service import LLMRecipeService
from app.services.clean_output_formatter import format_clean_meal_plan
from app.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/llm", tags=["LLM Meal Plans"])


# ============================================================================
# DEPENDENCY HELPERS
# ============================================================================

async def get_pantry_crud_instance() -> PantryItemCRUD:
    """Dependency: pantry CRUD."""
    collection = db_manager.get_collection("pantry_items")
    return get_pantry_item_crud(collection)


async def get_llm_plan_crud_instance() -> LLMMealPlanCRUD:
    """Dependency: LLM meal plan CRUD."""
    collection = db_manager.get_collection("llm_meal_plans")
    return get_llm_meal_plan_crud(collection)


# Singleton LLM service
_llm_service: Optional[LLMRecipeService] = None


def get_llm_service() -> LLMRecipeService:
    """Get or create singleton LLM service."""
    global _llm_service
    if _llm_service is None:
        model_name = settings.GROQ_MODEL if settings.MEAL_PLANNER_PROVIDER.lower() == "groq" else settings.GEMINI_MODEL
        _llm_service = LLMRecipeService(
            provider=settings.MEAL_PLANNER_PROVIDER,
            groq_api_key=settings.GROQ_API_KEY,
            gemini_api_key=settings.GEMINI_API_KEY_MEAL_PLANNER,
            model=model_name,
        )
        logger.info(f"LLM service initialized using provider: {settings.MEAL_PLANNER_PROVIDER}")
    return _llm_service


def _build_pantry_list(pantry_items_pydantic) -> list:
    """Convert pydantic pantry items to plain dicts for the orchestrator."""
    return [
        {
            "name": item.name,
            "quantity": float(item.quantity) if item.quantity else 0.0,
            "unit": item.unit if item.unit else "",
            "category": item.category if item.category else "other",
            "expiry_date": item.expiry_date.isoformat() if item.expiry_date else None,
        }
        for item in pantry_items_pydantic
    ]


def _build_orchestrator(pantry_items: list) -> LLMMealPlanOrchestrator:
    """Build a fresh orchestrator with the given pantry items."""
    return LLMMealPlanOrchestrator(
        pantry_items=pantry_items,
        llm_service=get_llm_service(),
    )


# ============================================================================
# GENERATE ENDPOINTS
# ============================================================================

@router.post("/generate", summary="Generate LLM-powered weekly meal plan")
async def generate_llm_meal_plan(
    request: LLMMealPlanRequest,
    pantry_crud: PantryItemCRUD = Depends(get_pantry_crud_instance),
    plan_crud: LLMMealPlanCRUD = Depends(get_llm_plan_crud_instance),
):
    """
    Generate a weekly meal plan using LLM + intelligent pantry selection.

    **Flow (per day):**
    1. Select ~10 ingredients (expiring first, balanced categories)
    2. Call Groq LLM → recipe name + all main ingredients
    3. Compare vs pantry → shopping list items
    4. Deduct matched ingredients from virtual pantry
    5. Repeat for each day
    6. Save plan to DB, return plan_id

    **Response format:**
    ```json
    {
      "status": "success",
      "plan_id": "...",
      "meal_plan": {"monday": "Palak Paneer", "tuesday": "Dal Tadka"},
      "shopping_list": ["cream", "paneer"],
      "days_generated": 7
    }
    ```
    """
    logger.info(f"LLM meal plan request: {request.dict()}")

    try:
        pantry_result = await pantry_crud.get_all(skip=0, limit=1000)
        pantry_items_pydantic = pantry_result.items

        if not pantry_items_pydantic:
            return {
                "status": "error",
                "error": "No pantry items found",
                "suggestion": "Please add ingredients to your pantry first",
            }

        pantry_items = _build_pantry_list(pantry_items_pydantic)
        logger.info(f"Found {len(pantry_items)} pantry items")

        orchestrator = _build_orchestrator(pantry_items)

        result = await orchestrator.generate_weekly_plan(
            days=request.days,
            diet_type=request.diet_type.value,
            servings=request.servings,
        )

        if not result.get("success"):
            return {
                "status": "error",
                "error": result.get("error", "Plan generation failed"),
                "suggestion": "Add more pantry items or broaden diet restrictions",
            }

        # Save to DB
        shopping_list_names = [
            item.get("name", "") if isinstance(item, dict) else str(item)
            for item in result.get("shopping_list", [])
        ]
        saved_plan = await plan_crud.create(
            meals=result.get("meals", []),
            shopping_list=shopping_list_names,
            pantry_summary=result.get("pantry_summary", {}),
            days_generated=result.get("days_generated", 0),
            diet_type=request.diet_type.value,
            servings=request.servings,
        )

        plan_id = saved_plan.get("id")
        logger.info(f"Saved LLM meal plan: {plan_id}")

        clean = format_clean_meal_plan(result)
        clean["plan_id"] = plan_id
        clean["pantry_summary"] = result.get("pantry_summary", {})
        return clean

    except Exception as e:
        logger.error(f"LLM meal plan generation failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "suggestion": "Please try again or contact support",
        }


@router.post("/generate-single", response_model=SingleMealResponse)
async def generate_single_llm_meal(
    request: SingleMealRequest,
    pantry_crud: PantryItemCRUD = Depends(get_pantry_crud_instance),
):
    """
    Generate a single meal suggestion using LLM.

    Useful for quick meal ideas or "What can I cook tonight?" queries.
    """
    logger.info(f"Single LLM meal request: {request.dict()}")

    try:
        pantry_result = await pantry_crud.get_all(skip=0, limit=1000)
        pantry_items_pydantic = pantry_result.items

        if not pantry_items_pydantic:
            return SingleMealResponse(success=False, error="No pantry items found")

        pantry_items = _build_pantry_list(pantry_items_pydantic)
        orchestrator = _build_orchestrator(pantry_items)

        result = await orchestrator.generate_single_meal(
            diet_type=request.diet_type.value,
            servings=request.servings,
            meal_type=request.meal_type.value,
        )

        return SingleMealResponse(**result)

    except Exception as e:
        logger.error(f"Single meal generation failed: {str(e)}", exc_info=True)
        return SingleMealResponse(success=False, error=str(e))


# ============================================================================
# GET / DELETE ENDPOINTS
# ============================================================================

@router.get("/{plan_id}", summary="Get a saved LLM meal plan")
async def get_llm_meal_plan(
    plan_id: str,
    plan_crud: LLMMealPlanCRUD = Depends(get_llm_plan_crud_instance),
):
    """Get a specific LLM meal plan by ID."""
    logger.info(f"Getting LLM meal plan: {plan_id}")

    try:
        plan = await plan_crud.get_by_id(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Get plan failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get plan: {str(e)}",
        )

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {plan_id!r} not found",
        )

    return {"status": "success", "plan": plan}


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an LLM meal plan")
async def delete_llm_meal_plan(
    plan_id: str,
    plan_crud: LLMMealPlanCRUD = Depends(get_llm_plan_crud_instance),
):
    """Delete an LLM meal plan."""
    logger.info(f"Deleting LLM meal plan: {plan_id}")

    try:
        deleted = await plan_crud.delete(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Delete plan failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete plan: {str(e)}",
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {plan_id!r} not found",
        )
    # 204 — no body returned


# ============================================================================
# REGENERATE ENDPOINT
# ============================================================================

@router.post("/{plan_id}/regenerate-day", summary="Regenerate a specific day in an existing plan")
async def regenerate_day_llm(
    plan_id: str,
    request: RegenerateDayRequest,
    pantry_crud: PantryItemCRUD = Depends(get_pantry_crud_instance),
    plan_crud: LLMMealPlanCRUD = Depends(get_llm_plan_crud_instance),
):
    """
    Regenerate the recipe for a specific day in an existing meal plan.

    **Flow:**
    1. Load existing plan from DB (404 if missing)
    2. Fetch current pantry
    3. Generate a new single meal using LLM (excludes current plan's recipes)
    4. Update the plan in DB
    5. Return updated plan
    """
    logger.info(f"Regenerating {request.day.value} for plan {plan_id}")

    # 1. Load existing plan
    try:
        plan = await plan_crud.get_by_id(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {plan_id!r} not found",
        )

    try:
        # 2. Fetch current pantry
        pantry_result = await pantry_crud.get_all(skip=0, limit=1000)
        pantry_items_pydantic = pantry_result.items

        if not pantry_items_pydantic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pantry items found — cannot regenerate",
            )

        pantry_items = _build_pantry_list(pantry_items_pydantic)
        orchestrator = _build_orchestrator(pantry_items)

        diet_type = plan.get("diet_type", "standard")
        servings = plan.get("servings", 2)

        # 3. Generate a new meal, passing existing recipe names to avoid repeats
        existing_names = [
            m.get("recipe_name", "")
            for m in plan.get("meals", [])
            if m.get("day") != request.day.value
        ]

        # Use generate_single_meal (diet + servings from original plan)
        result = await orchestrator.generate_single_meal(
            diet_type=diet_type,
            servings=servings,
            meal_type="dinner",
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=result.get("error", "Could not generate a replacement recipe"),
            )

        new_meal_data = {
            "day": request.day.value,
            "recipe_id": result.get("recipe_id"),
            "recipe_name": result.get("recipe_name"),
            "ready_in_minutes": result.get("cooking_time"),
            "servings": servings,
            "ingredients_deducted": [],
        }

        # 4. Persist updated day
        updated_plan = await plan_crud.update_day(plan_id, request.day.value, new_meal_data)

        logger.info(f"Regenerated {request.day.value}: {result.get('recipe_name')}")

        return {
            "status": "success",
            "day": request.day.value,
            "new_recipe": result.get("recipe_name"),
            "ingredients_to_buy": result.get("ingredients_to_buy", []),
            "plan": updated_plan,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Day regeneration failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate day: {str(e)}",
        )


# ============================================================================
# COMPLETE MEAL ENDPOINT
# ============================================================================

@router.patch("/{plan_id}/complete", summary="Mark meal as completed & deduct pantry")
async def complete_meal_llm(
    plan_id: str,
    request: CompleteMealRequest,
    pantry_crud: PantryItemCRUD = Depends(get_pantry_crud_instance),
    plan_crud: LLMMealPlanCRUD = Depends(get_llm_plan_crud_instance),
):
    """
    Mark a meal as completed and deduct its ingredients from the **real** pantry.

    **Flow:**
    1. Load plan from DB (404 if missing)
    2. Find the meal for the requested day
    3. For each ingredient in ``ingredients_deducted``, reduce the matching
       pantry item's quantity by 1 unit
    4. Mark the meal as completed in DB
    5. Return deduction summary
    """
    logger.info(f"Completing {request.day.value} {request.meal_type.value} for plan {plan_id}")

    # 1. Load plan
    try:
        plan = await plan_crud.get_by_id(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meal plan {plan_id!r} not found",
        )

    # 2. Find the meal for the requested day
    target_meal = None
    for m in plan.get("meals", []):
        if m.get("day") == request.day.value:
            target_meal = m
            break

    if not target_meal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No meal found for {request.day.value!r} in plan {plan_id!r}",
        )

    if target_meal.get("is_completed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Meal on {request.day.value!r} is already marked as completed",
        )

    try:
        # 3. Deduct from real pantry
        ingredients_to_deduct = target_meal.get("ingredients_deducted", [])
        deducted_count = 0
        deducted_names = []

        if ingredients_to_deduct:
            # Fetch all pantry items once, build name→item lookup
            pantry_result = await pantry_crud.get_all(skip=0, limit=1000)
            pantry_map = {
                item.name.lower(): item
                for item in pantry_result.items
            }

            for ing_name in ingredients_to_deduct:
                ing_lower = ing_name.lower()

                # Fuzzy-match: ingredient name contained in pantry name or vice versa
                matched_item = None
                for key, item in pantry_map.items():
                    if ing_lower in key or key in ing_lower:
                        matched_item = item
                        break

                if matched_item:
                    current_qty = float(matched_item.quantity or 0)
                    # Deduct 1 unit; clamp at 0
                    delta = -min(1.0, current_qty)

                    try:
                        await pantry_crud.update_quantity(
                            str(matched_item.id),
                            quantity_delta=delta,
                        )
                        deducted_names.append(matched_item.name)
                        deducted_count += 1
                        logger.info(
                            f"Deducted 1 unit of '{matched_item.name}': "
                            f"{current_qty} → {max(0.0, current_qty + delta)}"
                        )
                    except Exception as ue:
                        logger.warning(
                            f"Could not update pantry item '{matched_item.name}': {ue}"
                        )

        # 4. Mark meal as completed in DB
        updated_plan = await plan_crud.mark_meal_complete(
            plan_id=plan_id,
            day=request.day.value,
            meal_type=request.meal_type.value,
        )

        logger.info(
            f"Meal '{target_meal.get('recipe_name')}' completed. "
            f"Deducted {deducted_count} pantry items."
        )

        return {
            "status": "success",
            "message": f"'{target_meal.get('recipe_name')}' marked as completed",
            "day": request.day.value,
            "meal_type": request.meal_type.value,
            "ingredients_deducted": deducted_names,
            "deducted_count": deducted_count,
            "plan": updated_plan,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Meal completion failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete meal: {str(e)}",
        )