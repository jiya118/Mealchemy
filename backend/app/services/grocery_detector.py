"""
Grocery Detection Service using Groq Llama 4 Scout (Vision).

Sends uploaded grocery images to Groq's multimodal API, which can recognize
unlimited food categories (vegetables, fruits, spices, dairy, grains, Indian
grocery items, packaged goods, etc.) without any predefined class list.
"""
import json
import logging
import io
import re
import base64

from PIL import Image
from openai import OpenAI

from app.core.settings import settings
from app.schema.grocery_recognition import (
    DetectedItem,
    GroceryDetectionResponse,
)

logger = logging.getLogger(__name__)

# ─── Detection prompt ────────────────────────────────────────────────────────
DETECTION_PROMPT = """You are an expert grocery item identifier. Analyze this image and identify ALL grocery/food items visible.

For EACH distinct item you can see, provide:
- "item": The specific name of the item (e.g., "Capsicum (Bell Pepper)", "Sweet Potato", "Basmati Rice", "Amul Butter", "Turmeric Powder")
- "quantity": The exact count of that item visible in the image (count carefully!)
- "unit": The appropriate unit ("pieces", "grams", "kg", "liters", "ml", "packets", "bottles", "cans", "bunches")
- "category": One of these categories: "Fruits", "Vegetables", "Dairy", "Eggs", "Grains & Cereals", "Spices & Condiments", "Bakery & Snacks", "Beverages", "Meat & Seafood", "Pulses & Lentils", "Oils & Fats", "Packaged Foods", "Frozen Foods", "other"

Rules:
1. Count EACH individual item carefully. If you see 5 capsicums, the quantity should be 5.
2. Be specific with names. Don't just say "vegetable" — say "Capsicum (Bell Pepper)" or "Sweet Potato".
3. Include ALL visible items, even partially visible ones.
4. For packaged products, include brand names if readable.
5. If you're unsure about an item, make your best guess with the closest match.

Return ONLY a JSON array, no other text. Example format:
[
  {"item": "Capsicum (Bell Pepper)", "quantity": 5, "unit": "pieces", "category": "Vegetables"},
  {"item": "Sweet Potato", "quantity": 3, "unit": "pieces", "category": "Vegetables"},
  {"item": "Amul Butter", "quantity": 1, "unit": "packets", "category": "Dairy"}
]

If no grocery items are found, return an empty array: []"""


class GroceryDetector:
    """
    Grocery detector using Groq Llama 4 Scout (vision-capable).
    Uses the OpenAI-compatible Groq API for image analysis.
    """
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_client(self):
        if self._client is None:
            logger.info("Configuring Groq client for grocery detection...")
            self._client = OpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url=settings.GROQ_BASE_URL,
            )
            logger.info("Groq client ready.")

    def detect(self, image_bytes: bytes) -> GroceryDetectionResponse:
        """
        Send image to Groq Llama 4 Scout and parse detected grocery items.
        """
        self._ensure_client()

        # Get image dimensions
        pil_image = Image.open(io.BytesIO(image_bytes))
        img_width, img_height = pil_image.size

        # Prepare image as base64 data URI
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Detect content type
        pil_format = pil_image.format or "JPEG"
        mime_map = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
        mime_type = mime_map.get(pil_format.upper(), "image/jpeg")

        data_uri = f"data:{mime_type};base64,{image_b64}"

        # Send to Groq via OpenAI-compatible API
        logger.info(f"Sending image to Groq ({settings.GROQ_MODEL}) for recognition...")
        response = self._client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": DETECTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        },
                    ],
                }
            ],
            temperature=0.3,
            max_tokens=4096,
        )

        # Parse the JSON response
        raw_text = response.choices[0].message.content.strip()
        logger.info(f"Groq raw response: {raw_text[:200]}...")

        # Remove markdown code fences if present
        json_text = raw_text
        if json_text.startswith("```"):
            json_text = re.sub(r"^```(?:json)?\s*\n?", "", json_text)
            json_text = re.sub(r"\n?```\s*$", "", json_text)
        json_text = json_text.strip()

        try:
            items_data = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Groq response as JSON: {e}")
            logger.error(f"Raw response: {raw_text}")
            items_data = []

        # Build DetectedItem list
        detected_items = []
        total_instances = 0

        for item in items_data:
            if not isinstance(item, dict):
                continue

            name = item.get("item", "Unknown")
            quantity = max(1, int(item.get("quantity", 1)))
            unit = item.get("unit", "pieces")
            category = item.get("category", "other")

            total_instances += quantity

            detected_items.append(
                DetectedItem(
                    name=name,
                    quantity=quantity,
                    confidence=0.95,
                    category=category,
                    unit=unit,
                    bounding_boxes=[],
                )
            )

        logger.info(f"Groq detected {len(detected_items)} item types, {total_instances} total instances")

        return GroceryDetectionResponse(
            detected_items=detected_items,
            total_items_detected=len(detected_items),
            total_instances=total_instances,
            image_width=img_width,
            image_height=img_height,
        )


grocery_detector = GroceryDetector()
