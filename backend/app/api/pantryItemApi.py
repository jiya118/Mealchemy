"""
API endpoints for pantry items.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional

from app.database.db import get_database, db_manager
from app.crud.pantryItemCrud import get_pantry_item_crud, PantryItemCRUD
from app.schema.pantryItem import (
    PantryItemCreate,
    PantryItemUpdate,
    PantryItemResponse,
    PantryItemList,
    CategoryEnum
)

router = APIRouter(prefix="/pantry-items", tags=["Pantry Items"])


async def get_crud() -> PantryItemCRUD:
    """Dependency to get CRUD instance."""
    collection = db_manager.get_collection("pantry_items")
    return get_pantry_item_crud(collection)


@router.post(
    "",
    response_model=PantryItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new pantry item"
)
async def create_pantry_item(
    item: PantryItemCreate,
    crud: PantryItemCRUD = Depends(get_crud)
):
    """
    Create a new pantry item with the following information:
    
    - **name**: Item name (required)
    - **category**: Item category
    - **quantity**: Current quantity
    - **unit**: Measurement unit
    - **location**: Storage location
    - **expiry_date**: Expiration date (optional)
    - **notes**: Additional notes (optional)
    """
    return await crud.create(item)


@router.get(
    "",
    response_model=PantryItemList,
    summary="Get all pantry items"
)
async def get_pantry_items(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    category: Optional[CategoryEnum] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name"),
    sort_by: str = Query("name", description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    crud: PantryItemCRUD = Depends(get_crud)
):
    """
    Get a paginated list of pantry items with optional filtering and sorting.
    """
    skip = (page - 1) * page_size
    
    return await crud.get_all(
        skip=skip,
        limit=page_size,
        category=category,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.get(
    "/expiring-soon",
    response_model=list[PantryItemResponse],
    summary="Get items expiring soon"
)
async def get_expiring_items(
    days: int = Query(7, ge=1, le=365, description="Days to look ahead"),
    limit: int = Query(100, ge=1, le=500, description="Maximum items to return"),
    crud: PantryItemCRUD = Depends(get_crud)
):
    """
    Get items that are expiring within the specified number of days.
    """
    return await crud.get_expiring_soon(days=days, limit=limit)


@router.get(
    "/low-stock",
    response_model=list[PantryItemResponse],
    summary="Get low stock items"
)
async def get_low_stock_items(
    threshold: float = Query(1.0, ge=0, description="Quantity threshold"),
    limit: int = Query(100, ge=1, le=500, description="Maximum items to return"),
    crud: PantryItemCRUD = Depends(get_crud)
):
    """
    Get items with quantity at or below the specified threshold.
    """
    return await crud.get_low_stock(threshold=threshold, limit=limit)


@router.get(
    "/{item_id}",
    response_model=PantryItemResponse,
    summary="Get a pantry item by ID"
)
async def get_pantry_item(
    item_id: str,
    crud: PantryItemCRUD = Depends(get_crud)
):
    """
    Get a specific pantry item by its ID.
    """
    item = await crud.get_by_id(item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pantry item with ID {item_id} not found"
        )
    
    return item


@router.put(
    "/{item_id}",
    response_model=PantryItemResponse,
    summary="Update a pantry item"
)
async def update_pantry_item(
    item_id: str,
    item_update: PantryItemUpdate,
    crud: PantryItemCRUD = Depends(get_crud)
):
    """
    Update a pantry item. Only provided fields will be updated.
    """
    item = await crud.update(item_id, item_update)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pantry item with ID {item_id} not found"
        )
    
    return item


@router.patch(
    "/{item_id}/quantity",
    response_model=PantryItemResponse,
    summary="Adjust item quantity"
)
async def adjust_quantity(
    item_id: str,
    delta: float = Query(..., description="Amount to add (can be negative)"),
    crud: PantryItemCRUD = Depends(get_crud)
):
    """
    Adjust the quantity of an item by adding a delta value.
    Use negative values to decrease quantity.
    """
    item = await crud.update_quantity(item_id, delta)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pantry item with ID {item_id} not found"
        )
    
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a pantry item"
)
async def delete_pantry_item(
    item_id: str,
    crud: PantryItemCRUD = Depends(get_crud)
):
    """
    Delete a pantry item by its ID.
    """
    deleted = await crud.delete(item_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pantry item with ID {item_id} not found"
        )
    
    return None