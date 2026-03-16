"""
Pydantic schemas for pantry item models.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


class CategoryEnum(str, Enum):
    """Pantry item categories."""
    GRAINS = "grains"
    GRAINS_AND_CEREALS = "Grains & Cereals"
    CANNED_GOODS = "canned_goods"
    SPICES = "spices"
    SPICES_AND_CONDIMENTS = "Spices & Condiments"
    CONDIMENTS = "condiments"
    BAKING = "baking"
    BAKERY_AND_SNACKS = "Bakery & Snacks"
    SNACKS = "snacks"
    BEVERAGES = "Beverages"
    DAIRY = "Dairy"
    EGGS = "Eggs"
    VEGETABLES = "Vegetables"
    FRUITS = "Fruits"
    OILS = "Oils"
    SUGAR_AND_SWEETENERS = "Sugar & Sweeteners"
    FROZEN = "frozen"
    OTHER = "other"
    PULSES_AND_LENTILS = "Pulses & Lentils"


class UnitEnum(str, Enum):
    """Measurement units."""
    PIECES = "pieces"
    GRAMS = "grams"
    KILOGRAMS = "kilograms"
    KG = "kg"
    MILLILITERS = "milliliters"
    ML = "ml"
    LITERS = "liters"
    LITER = "liter"
    OUNCES = "ounces"
    POUNDS = "pounds"
    CUPS = "cups"
    TABLESPOONS = "tablespoons"
    TEASPOONS = "teaspoons"
    SLICES = "slices"
    PACK = "pack"
    PACKS = "packs"


class PantryItemBase(BaseModel):
    """Base schema for pantry item."""
    name: str = Field(..., min_length=1, max_length=100)
    category: CategoryEnum = Field(default=CategoryEnum.OTHER)
    quantity: float = Field(..., ge=0)
    unit: UnitEnum = Field(default=UnitEnum.PIECES)
    expiry_date: Optional[datetime] = None
    
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        """Validate name is not just whitespace."""
        if not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip()


class PantryItemCreate(PantryItemBase):
    """Schema for creating a new pantry item."""
    pass


class PantryItemUpdate(BaseModel):
    """Schema for updating a pantry item. All fields optional."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[CategoryEnum] = None
    quantity: Optional[float] = Field(None, ge=0)
    unit: Optional[UnitEnum] = None
    expiry_date: Optional[datetime] = None
    
    @field_validator('name')
    @classmethod
    def name_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        """Validate name is not just whitespace if provided."""
        if v is not None and not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip() if v else None


class PantryItemInDB(PantryItemBase):
    """Schema for pantry item as stored in database."""
    id: str = Field(..., alias="_id")
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "Basmati Rice",
                "category": "grains",
                "quantity": 5.0,
                "unit": "kilograms",
                "expiry_date": "2025-12-31T00:00:00",
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00"
            }
        }
    }


class PantryItemResponse(PantryItemInDB):
    """Schema for pantry item API response."""
    pass


class PantryItemList(BaseModel):
    """Schema for paginated list of pantry items."""
    items: list[PantryItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 42,
                "page": 1,
                "page_size": 10,
                "total_pages": 5
            }
        }
    }