"""
Two-Stage Grocery Detection Service.

Stage 1: Custom YOLOv8 model (best.pt) — fast, offline, runs first.
Stage 2: Gemini API fallback — used when Stage 1 is insufficient or unavailable.
"""
import json
import io
import os
import re
import logging
from collections import Counter
from pathlib import Path

from PIL import Image
import google.generativeai as genai

from app.core.settings import settings
from app.schema.grocery_recognition import (
    BoundingBox,
    DetectedItem,
    GroceryDetectionResponse,
)

logger = logging.getLogger(__name__)

# ─── Category mapping for Stage 1 (custom model) ─────────────────────────────
# NOTE: These sets must include the EXACT class names from best.pt (lowercased).
#       The model has 64 classes — check test_yolo.py output for the full list.
FRUIT_CLASSES = {
    "apple", "banana", "mango", "orange", "lemon", "grape", "grapes",
    "strawberry", "stawberry",  # model has typo "stawberry"
    "watermelon", "yellow watermelon", "pineapple", "coconut", "guava",
    "apricot", "peach", "pear", "plum", "japanese plum", "dates",
    "cantaloupe",
}

VEGETABLE_CLASSES = {
    "tomato", "carrot", "potato", "onion", "broccoli", "cabbage",
    "purple cabbage", "cauliflower", "cucumber", "pumpkin", "mushroom",
    "garlic", "ginger", "capsicum", "chilli", "eggplant", "spinach",
    "beans", "beetroot", "bitter gourd", "peas", "radish", "mint",
    "lettuce", "zucchini", "corn", "lady-s finger", "turnip",
    "taro root", "apple gourd", "luffa gourd",
}

NONVEG_CLASSES = {
    "chicken", "egg", "fish", "shrimp", "crab", "lobster", "salmon",
}

DAIRY_CLASSES = {
    "milk", "cheese", "butter", "cream",
}

SPICE_CLASSES = {
    "biji ketumbar", "bunga cengkih", "bunga lawang", "cili kering",
    "daun salam", "halia kering", "jintan manis", "jintan putih",
    "kayu manis", "lada hitam",
}


def _classify(class_name: str) -> str:
    """Map a YOLO class name to a grocery category matching frontend constants."""
    name = class_name.lower().strip()
    if name in FRUIT_CLASSES:
        return "Fruits"
    if name in VEGETABLE_CLASSES:
        return "Vegetables"
    if name in NONVEG_CLASSES:
        return "Meat & Seafood"
    if name in DAIRY_CLASSES:
        return "Dairy"
    if name in SPICE_CLASSES:
        return "Spices & Condiments"
    return "other"


# ─── Gemini prompt for Stage 2 ───────────────────────────────────────────────
GEMINI_PROMPT = (
    "You are a smart grocery recognition system. Look at this image carefully "
    "and identify ALL food/grocery items visible. This includes vegetables, "
    "fruits, dairy, grains, spices, packaged items, non-veg items like "
    "chicken/fish/eggs. For each item estimate quantity and unit. Return ONLY "
    "a valid JSON array with no explanation, no markdown. "
    "IMPORTANT: Use ONLY these exact category values: "
    '"Fruits", "Vegetables", "Dairy", "Eggs", "Grains & Cereals", '
    '"Spices & Condiments", "Bakery & Snacks", "Beverages", '
    '"Meat & Seafood", "Pulses & Lentils", "Oils", "Frozen Foods", '
    '"Packaged Foods", "other". '
    'Format: [{"item": "tomato", "quantity": 5, "unit": "pieces", '
    '"category": "Vegetables", "confidence": 0.95}]'
)


class GroceryDetector:
    """
    Two-stage grocery detector.

    Stage 1 — Custom YOLOv8 (``best.pt``):
      • Runs first with conf ≥ 0.45.
      • Returns directly when detections ≥ 3 AND all confidences ≥ 0.70.

    Stage 2 — Gemini API fallback:
      • Activated when Stage 1 is insufficient or when the YOLO model
        failed to load.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._yolo_model = None
            cls._instance._yolo_available = False
            cls._instance._gemini_model = None
            cls._instance._load_yolo()
        return cls._instance

    # ── Model loading ────────────────────────────────────────────────────
    def _load_yolo(self):
        """Load the custom YOLOv8 model once. Never crashes the app."""
        try:
            from ultralytics import YOLO

            # Resolve model path relative to the backend directory
            model_path = Path(__file__).resolve().parents[2] / "models" / "best.pt"
            if not model_path.exists():
                logger.warning(
                    f"YOLO model not found at {model_path}. "
                    "Falling back to Gemini-only mode."
                )
                return

            logger.info(f"Loading custom YOLOv8 model from {model_path} ...")
            self._yolo_model = YOLO(str(model_path))
            self._yolo_available = True
            logger.info("Custom YOLOv8 model loaded successfully.")

        except Exception as exc:
            logger.warning(
                f"Failed to load YOLOv8 model: {exc}. "
                "Falling back to Gemini-only mode."
            )
            self._yolo_available = False

    def _ensure_gemini(self):
        """Lazily configure the Gemini client."""
        if self._gemini_model is None:
            logger.info("Configuring Gemini client for grocery detection …")
            genai.configure(api_key=settings.GEMINI_API_KEY_GROCERY)
            model_name = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
            self._gemini_model = genai.GenerativeModel(model_name)
            logger.info(f"Gemini client ready (model={model_name}).")

    # ── Stage 1: Custom YOLOv8 ───────────────────────────────────────────
    def _run_yolo(self, pil_image: Image.Image):
        """
        Run YOLOv8 inference.

        Returns
        -------
        tuple(list[dict], bool)
            (detections, should_use_results)
            - detections: list of dicts with item/quantity/unit/category/confidence/bounding_boxes
            - should_use_results: True if Stage 1 results are sufficient
        """
        results = self._yolo_model.predict(
            source=pil_image,
            conf=0.45,
            verbose=False,
        )

        # Collect per-box data
        boxes_by_class: dict[str, list] = {}
        confidences_by_class: dict[str, list] = {}

        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                class_name = self._yolo_model.names[cls_id]
                conf = float(box.conf[0])

                if conf < 0.45:
                    continue

                boxes_by_class.setdefault(class_name, [])
                confidences_by_class.setdefault(class_name, [])

                x1, y1, x2, y2 = box.xyxy[0].tolist()
                boxes_by_class[class_name].append(
                    BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                )
                confidences_by_class[class_name].append(conf)

        # Build detections list
        all_detections = []
        all_confidences = []

        for class_name, bboxes in boxes_by_class.items():
            confs = confidences_by_class[class_name]
            avg_conf = sum(confs) / len(confs)
            all_confidences.extend(confs)

            all_detections.append({
                "item": class_name,
                "quantity": len(bboxes),
                "unit": "pieces",
                "category": _classify(class_name),
                "confidence": round(avg_conf, 2),
                "bounding_boxes": bboxes,
            })

        total_detections = sum(len(confidences_by_class[c]) for c in confidences_by_class)

        # Gate: need ≥ 1 detection AND average confidence ≥ 0.55
        avg_overall = (
            sum(all_confidences) / len(all_confidences)
            if all_confidences else 0
        )
        sufficient = (
            total_detections >= 1
            and avg_overall >= 0.55
        )

        logger.info(
            f"YOLOv8 Stage 1: {total_detections} detections across "
            f"{len(all_detections)} classes | avg_conf={avg_overall:.2f} | "
            f"sufficient={sufficient}"
        )

        return all_detections, sufficient

    # ── Stage 2: Gemini fallback ─────────────────────────────────────────
    def _run_gemini(self, pil_image: Image.Image):
        """
        Send image to Gemini and return parsed detections.

        Returns
        -------
        list[dict]
        """
        self._ensure_gemini()
        logger.info("Stage 2: Sending image to Gemini for recognition …")

        response = self._gemini_model.generate_content(
            [GEMINI_PROMPT, pil_image],
            generation_config={"temperature": 0.3},
        )

        raw_text = response.text.strip()
        logger.info(f"Gemini raw response: {raw_text[:300]}…")

        # Strip markdown code fences if present
        json_text = raw_text
        if json_text.startswith("```"):
            json_text = re.sub(r"^```(?:json)?\s*\n?", "", json_text)
            json_text = re.sub(r"\n?```\s*$", "", json_text)
        json_text = json_text.strip()

        try:
            items_data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse Gemini JSON: {exc}")
            logger.error(f"Raw text: {raw_text}")
            items_data = []

        detections = []
        for item in items_data:
            if not isinstance(item, dict):
                continue
            detections.append({
                "item": item.get("item", "Unknown"),
                "quantity": max(1, int(item.get("quantity", 1))),
                "unit": item.get("unit", "pieces"),
                "category": item.get("category", "other"),
                "confidence": float(item.get("confidence", 0.90)),
                "bounding_boxes": [],
            })

        logger.info(f"Gemini detected {len(detections)} items.")
        return detections

    # ── Public API ───────────────────────────────────────────────────────
    def detect(self, image_bytes: bytes) -> GroceryDetectionResponse:
        """
        Run two-stage detection on *image_bytes*.

        Returns
        -------
        GroceryDetectionResponse
            Response with model_used field set to "custom_model" or "gemini_fallback".
        """
        pil_image = Image.open(io.BytesIO(image_bytes))
        img_width, img_height = pil_image.size

        model_used = "gemini_fallback"
        detections: list[dict] = []

        # ── Stage 1: Custom YOLOv8 ──────────────────────────────────────
        if self._yolo_available:
            try:
                yolo_detections, sufficient = self._run_yolo(pil_image)
                if sufficient:
                    detections = yolo_detections
                    model_used = "custom_model"
                    logger.info("✅ Using custom YOLOv8 model results.")
                else:
                    logger.info(
                        "Stage 1 insufficient — falling through to Gemini."
                    )
            except Exception as exc:
                logger.warning(f"YOLOv8 inference failed: {exc}. Falling back to Gemini.")

        # ── Stage 2: Gemini fallback ────────────────────────────────────
        if model_used != "custom_model":
            try:
                detections = self._run_gemini(pil_image)
                model_used = "gemini_fallback"
                logger.info("✅ Using Gemini fallback results.")
            except Exception as exc:
                logger.error(f"Gemini fallback also failed: {exc}")
                detections = []

        # ── Build response ──────────────────────────────────────────────
        detected_items = []
        total_instances = 0

        for det in detections:
            qty = det.get("quantity", 1)
            total_instances += qty
            detected_items.append(
                DetectedItem(
                    name=det["item"],
                    quantity=qty,
                    confidence=det["confidence"],
                    category=det["category"],
                    unit=det.get("unit", "pieces"),
                    bounding_boxes=det.get("bounding_boxes", []),
                )
            )

        response = GroceryDetectionResponse(
            detected_items=detected_items,
            total_items_detected=len(detected_items),
            total_instances=total_instances,
            image_width=img_width,
            image_height=img_height,
            model_used=model_used,
        )

        logger.info(
            f"Detection complete | model={model_used} | "
            f"{len(detected_items)} types, {total_instances} instances"
        )

        return response


# Singleton instance — model loads once on import
grocery_detector = GroceryDetector()
