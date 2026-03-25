"""
API endpoint for grocery recognition via image upload.
"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status

from app.schema.grocery_recognition import GroceryDetectionResponse
from app.services.grocery_detector import grocery_detector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grocery-recognition", tags=["Grocery Recognition"])

# Allowed image MIME types
ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
}

# 10 MB max file size
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post(
    "/detect",
    response_model=GroceryDetectionResponse,
    summary="Detect grocery items in an uploaded image",
    description=(
        "Upload a photo of groceries and the system will detect items "
        "using Google Gemini 1.5 Flash. Returns a list of detected items "
        "with estimated quantities and categories."
    ),
)
async def detect_groceries(
    file: UploadFile = File(
        ...,
        description="Image file (JPEG, PNG, or WebP, max 10 MB)"
    ),
):
    """
    Detect grocery items in an uploaded image using Gemini AI.

    - Accepts JPEG, PNG, WebP images up to 10 MB
    - Returns detected items with name, quantity, category, and unit
    - User should review/edit results before saving to pantry
    """
    # ── Validate file type ────────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid file type: {file.content_type}. "
                f"Allowed types: JPEG, PNG, WebP."
            ),
        )

    # ── Read and validate file size ───────────────────────────────────
    image_bytes = await file.read()

    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is 10 MB.",
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── Run detection ─────────────────────────────────────────────────
    try:
        result = grocery_detector.detect(image_bytes=image_bytes)
        logger.info(
            f"Grocery detection complete: {result.total_items_detected} types, "
            f"{result.total_instances} instances"
        )
        return result

    except Exception as e:
        logger.error(f"Grocery detection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Detection failed: {str(e)}",
        )
