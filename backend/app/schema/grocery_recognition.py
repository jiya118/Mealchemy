"""
Pydantic schemas for grocery recognition (computer vision) responses.
"""
from pydantic import BaseModel, Field
from typing import Optional


class BoundingBox(BaseModel):
    """Bounding box coordinates for a detected item."""
    x1: float = Field(..., description="Top-left X coordinate")
    y1: float = Field(..., description="Top-left Y coordinate")
    x2: float = Field(..., description="Bottom-right X coordinate")
    y2: float = Field(..., description="Bottom-right Y coordinate")


class DetectedItem(BaseModel):
    """A single grocery item detected in the image."""
    name: str = Field(..., description="Pantry-friendly item name")
    quantity: int = Field(default=1, ge=1, description="Estimated count")
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Average detection confidence (0-1)"
    )
    category: str = Field(
        default="other",
        description="Auto-mapped pantry category"
    )
    unit: str = Field(
        default="pieces",
        description="Default measurement unit"
    )
    bounding_boxes: list[BoundingBox] = Field(
        default_factory=list,
        description="Bounding boxes of all instances detected"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Apple",
                "quantity": 3,
                "confidence": 0.92,
                "category": "Fruits",
                "unit": "pieces",
                "bounding_boxes": [
                    {"x1": 120, "y1": 80, "x2": 220, "y2": 180}
                ]
            }
        }
    }


class GroceryDetectionResponse(BaseModel):
    """Response from the grocery detection endpoint."""
    detected_items: list[DetectedItem] = Field(
        default_factory=list,
        description="List of detected grocery items"
    )
    total_items_detected: int = Field(
        default=0, ge=0,
        description="Total number of unique item types detected"
    )
    total_instances: int = Field(
        default=0, ge=0,
        description="Total number of individual instances detected"
    )
    image_width: int = Field(..., description="Original image width in pixels")
    image_height: int = Field(..., description="Original image height in pixels")
    model_used: str = Field(
        default="gemini_fallback",
        description="Which model produced the results: 'custom_model' or 'gemini_fallback'"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "detected_items": [],
                "total_items_detected": 3,
                "total_instances": 7,
                "image_width": 1920,
                "image_height": 1080,
                "model_used": "custom_model"
            }
        }
    }
