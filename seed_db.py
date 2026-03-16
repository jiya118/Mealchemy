"""
PantryMind — Seed Database Script
==================================
Populates the 'pantry_items' collection in MongoDB Atlas
with 35 realistic sample pantry items.

Run:  python seed_db.py
"""

from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "pantrymind")

# ─── Helper ───────────────────────────────────────────────────────
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def date_offset(days: int) -> datetime:
    """Return a datetime 'days' from today (negative = past)."""
    return today + timedelta(days=days)


# ─── Seed Data ────────────────────────────────────────────────────
pantry_items = [
    # ── Grains & Cereals ──────────────────────────────────────────
    {
        "item_name": "Basmati Rice",
        "category": "Grains & Cereals",
        "quantity": 5,
        "unit": "kg",
        "purchase_date": date_offset(-10),
        "expiry_date": date_offset(180),
        "is_expired": False,
    },
    {
        "item_name": "Whole Wheat Flour (Atta)",
        "category": "Grains & Cereals",
        "quantity": 10,
        "unit": "kg",
        "purchase_date": date_offset(-7),
        "expiry_date": date_offset(120),
        "is_expired": False,
    },
    {
        "item_name": "Oats",
        "category": "Grains & Cereals",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-14),
        "expiry_date": date_offset(150),
        "is_expired": False,
    },
    {
        "item_name": "Poha (Flattened Rice)",
        "category": "Grains & Cereals",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-20),
        "expiry_date": date_offset(90),
        "is_expired": False,
    },
    {
        "item_name": "Pasta",
        "category": "Grains & Cereals",
        "quantity": 400,
        "unit": "grams",
        "purchase_date": date_offset(-5),
        "expiry_date": date_offset(200),
        "is_expired": False,
    },
    {
        "item_name": "Semolina (Suji)",
        "category": "Grains & Cereals",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-12),
        "expiry_date": date_offset(100),
        "is_expired": False,
    },

    # ── Pulses & Lentils ──────────────────────────────────────────
    {
        "item_name": "Toor Dal",
        "category": "Pulses & Lentils",
        "quantity": 2,
        "unit": "kg",
        "purchase_date": date_offset(-15),
        "expiry_date": date_offset(150),
        "is_expired": False,
    },
    {
        "item_name": "Moong Dal",
        "category": "Pulses & Lentils",
        "quantity": 1,
        "unit": "kg",
        "purchase_date": date_offset(-15),
        "expiry_date": date_offset(150),
        "is_expired": False,
    },
    {
        "item_name": "Chana Dal",
        "category": "Pulses & Lentils",
        "quantity": 1,
        "unit": "kg",
        "purchase_date": date_offset(-10),
        "expiry_date": date_offset(160),
        "is_expired": False,
    },
    {
        "item_name": "Rajma (Kidney Beans)",
        "category": "Pulses & Lentils",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-8),
        "expiry_date": date_offset(180),
        "is_expired": False,
    },
    {
        "item_name": "Masoor Dal",
        "category": "Pulses & Lentils",
        "quantity": 1,
        "unit": "kg",
        "purchase_date": date_offset(-12),
        "expiry_date": date_offset(140),
        "is_expired": False,
    },

    # ── Dairy ─────────────────────────────────────────────────────
    {
        "item_name": "Milk",
        "category": "Dairy",
        "quantity": 2,
        "unit": "liters",
        "purchase_date": date_offset(-1),
        "expiry_date": date_offset(2),           # ⚠️ expiring soon
        "is_expired": False,
    },
    {
        "item_name": "Paneer",
        "category": "Dairy",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-2),
        "expiry_date": date_offset(1),            # ⚠️ expiring tomorrow
        "is_expired": False,
    },
    {
        "item_name": "Curd (Yogurt)",
        "category": "Dairy",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-5),
        "expiry_date": date_offset(-1),           # ❌ expired yesterday
        "is_expired": True,
    },
    {
        "item_name": "Butter",
        "category": "Dairy",
        "quantity": 200,
        "unit": "grams",
        "purchase_date": date_offset(-3),
        "expiry_date": date_offset(30),
        "is_expired": False,
    },
    {
        "item_name": "Cheese Slices",
        "category": "Dairy",
        "quantity": 10,
        "unit": "slices",
        "purchase_date": date_offset(-4),
        "expiry_date": date_offset(20),
        "is_expired": False,
    },

    # ── Eggs ──────────────────────────────────────────────────────
    {
        "item_name": "Eggs",
        "category": "Eggs",
        "quantity": 12,
        "unit": "pieces",
        "purchase_date": date_offset(-2),
        "expiry_date": date_offset(12),
        "is_expired": False,
    },

    # ── Vegetables ────────────────────────────────────────────────
    {
        "item_name": "Onions",
        "category": "Vegetables",
        "quantity": 3,
        "unit": "kg",
        "purchase_date": date_offset(-4),
        "expiry_date": date_offset(10),
        "is_expired": False,
    },
    {
        "item_name": "Tomatoes",
        "category": "Vegetables",
        "quantity": 2,
        "unit": "kg",
        "purchase_date": date_offset(-2),
        "expiry_date": date_offset(5),
        "is_expired": False,
    },
    {
        "item_name": "Potatoes",
        "category": "Vegetables",
        "quantity": 3,
        "unit": "kg",
        "purchase_date": date_offset(-5),
        "expiry_date": date_offset(20),
        "is_expired": False,
    },
    {
        "item_name": "Spinach",
        "category": "Vegetables",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-1),
        "expiry_date": date_offset(3),            # ⚠️ expiring soon
        "is_expired": False,
    },
    {
        "item_name": "Capsicum",
        "category": "Vegetables",
        "quantity": 4,
        "unit": "pieces",
        "purchase_date": date_offset(-2),
        "expiry_date": date_offset(6),
        "is_expired": False,
    },
    {
        "item_name": "Carrots",
        "category": "Vegetables",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-3),
        "expiry_date": date_offset(10),
        "is_expired": False,
    },
    {
        "item_name": "Green Chillies",
        "category": "Vegetables",
        "quantity": 100,
        "unit": "grams",
        "purchase_date": date_offset(-1),
        "expiry_date": date_offset(5),
        "is_expired": False,
    },
    {
        "item_name": "Ginger",
        "category": "Vegetables",
        "quantity": 100,
        "unit": "grams",
        "purchase_date": date_offset(-3),
        "expiry_date": date_offset(10),
        "is_expired": False,
    },
    {
        "item_name": "Garlic",
        "category": "Vegetables",
        "quantity": 200,
        "unit": "grams",
        "purchase_date": date_offset(-5),
        "expiry_date": date_offset(15),
        "is_expired": False,
    },

    # ── Fruits ────────────────────────────────────────────────────
    {
        "item_name": "Bananas",
        "category": "Fruits",
        "quantity": 6,
        "unit": "pieces",
        "purchase_date": date_offset(-2),
        "expiry_date": date_offset(4),
        "is_expired": False,
    },
    {
        "item_name": "Apples",
        "category": "Fruits",
        "quantity": 4,
        "unit": "pieces",
        "purchase_date": date_offset(-3),
        "expiry_date": date_offset(10),
        "is_expired": False,
    },
    {
        "item_name": "Lemons",
        "category": "Fruits",
        "quantity": 6,
        "unit": "pieces",
        "purchase_date": date_offset(-2),
        "expiry_date": date_offset(12),
        "is_expired": False,
    },

    # ── Spices & Condiments ───────────────────────────────────────
    {
        "item_name": "Red Chili Powder",
        "category": "Spices & Condiments",
        "quantity": 200,
        "unit": "grams",
        "purchase_date": date_offset(-20),
        "expiry_date": date_offset(300),
        "is_expired": False,
    },
    {
        "item_name": "Turmeric Powder",
        "category": "Spices & Condiments",
        "quantity": 100,
        "unit": "grams",
        "purchase_date": date_offset(-20),
        "expiry_date": date_offset(300),
        "is_expired": False,
    },
    {
        "item_name": "Garam Masala",
        "category": "Spices & Condiments",
        "quantity": 100,
        "unit": "grams",
        "purchase_date": date_offset(-15),
        "expiry_date": date_offset(250),
        "is_expired": False,
    },
    {
        "item_name": "Cumin Seeds",
        "category": "Spices & Condiments",
        "quantity": 100,
        "unit": "grams",
        "purchase_date": date_offset(-25),
        "expiry_date": date_offset(280),
        "is_expired": False,
    },
    {
        "item_name": "Salt",
        "category": "Spices & Condiments",
        "quantity": 1,
        "unit": "kg",
        "purchase_date": date_offset(-30),
        "expiry_date": date_offset(365),
        "is_expired": False,
    },
    {
        "item_name": "Black Pepper Powder",
        "category": "Spices & Condiments",
        "quantity": 50,
        "unit": "grams",
        "purchase_date": date_offset(-18),
        "expiry_date": date_offset(270),
        "is_expired": False,
    },
    {
        "item_name": "Coriander Powder",
        "category": "Spices & Condiments",
        "quantity": 100,
        "unit": "grams",
        "purchase_date": date_offset(-22),
        "expiry_date": date_offset(260),
        "is_expired": False,
    },

    # ── Oils ──────────────────────────────────────────────────────
    {
        "item_name": "Mustard Oil",
        "category": "Oils",
        "quantity": 1,
        "unit": "liter",
        "purchase_date": date_offset(-10),
        "expiry_date": date_offset(180),
        "is_expired": False,
    },
    {
        "item_name": "Olive Oil",
        "category": "Oils",
        "quantity": 500,
        "unit": "ml",
        "purchase_date": date_offset(-8),
        "expiry_date": date_offset(200),
        "is_expired": False,
    },
    {
        "item_name": "Ghee",
        "category": "Oils",
        "quantity": 500,
        "unit": "ml",
        "purchase_date": date_offset(-6),
        "expiry_date": date_offset(180),
        "is_expired": False,
    },

    # ── Beverages ─────────────────────────────────────────────────
    {
        "item_name": "Tea (Chai Leaves)",
        "category": "Beverages",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-10),
        "expiry_date": date_offset(180),
        "is_expired": False,
    },
    {
        "item_name": "Coffee Powder",
        "category": "Beverages",
        "quantity": 200,
        "unit": "grams",
        "purchase_date": date_offset(-8),
        "expiry_date": date_offset(150),
        "is_expired": False,
    },

    # ── Bakery & Snacks ───────────────────────────────────────────
    {
        "item_name": "Bread",
        "category": "Bakery & Snacks",
        "quantity": 1,
        "unit": "pack",
        "purchase_date": date_offset(-10),
        "expiry_date": date_offset(-2),           # ❌ expired 2 days ago
        "is_expired": True,
    },
    {
        "item_name": "Biscuits",
        "category": "Bakery & Snacks",
        "quantity": 3,
        "unit": "packs",
        "purchase_date": date_offset(-7),
        "expiry_date": date_offset(60),
        "is_expired": False,
    },
    {
        "item_name": "Maggi Noodles",
        "category": "Bakery & Snacks",
        "quantity": 8,
        "unit": "packs",
        "purchase_date": date_offset(-5),
        "expiry_date": date_offset(200),
        "is_expired": False,
    },

    # ── Sugar & Sweeteners ────────────────────────────────────────
    {
        "item_name": "Sugar",
        "category": "Sugar & Sweeteners",
        "quantity": 1,
        "unit": "kg",
        "purchase_date": date_offset(-20),
        "expiry_date": date_offset(365),
        "is_expired": False,
    },
    {
        "item_name": "Honey",
        "category": "Sugar & Sweeteners",
        "quantity": 250,
        "unit": "grams",
        "purchase_date": date_offset(-14),
        "expiry_date": date_offset(300),
        "is_expired": False,
    },
    {
        "item_name": "Jaggery (Gud)",
        "category": "Sugar & Sweeteners",
        "quantity": 500,
        "unit": "grams",
        "purchase_date": date_offset(-18),
        "expiry_date": date_offset(200),
        "is_expired": False,
    },
]


# ─── Main ─────────────────────────────────────────────────────────
def seed():
    print("🌱 PantryMind — Seed Script")
    print("=" * 50)

    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    collection = db["pantry_items"]

    # Drop existing data for a clean slate
    collection.drop()
    print("🗑️  Cleared existing pantry_items collection.\n")

    # Insert seed data
    result = collection.insert_many(pantry_items)
    print(f"✅ Inserted {len(result.inserted_ids)} pantry items.\n")

    # Print summary
    print(f"{'#':<4} {'Item':<30} {'Qty':>6} {'Unit':<10} {'Category':<22} {'Status'}")
    print("-" * 90)

    for i, item in enumerate(pantry_items, 1):
        expiry: datetime = item["expiry_date"]
        days_left = (expiry - today).days
        status = "❌ EXPIRED" if item["is_expired"] else (
            "⚠️  EXPIRING SOON" if days_left <= 3 else "✅ Fresh"
        )
        print(f"{i:<4} {item['item_name']:<30} {item['quantity']:>6} {item['unit']:<10} {item['category']:<22} {status}")

    # Category summary
    categories = {}
    for item in pantry_items:
        cat = item["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n{'─' * 50}")
    print("📊 Category Breakdown:")
    for cat, count in categories.items():
        print(f"   {cat:<25} → {count} items")

    expired = sum(1 for item in pantry_items if item["is_expired"])
    expiring = sum(
        1 for item in pantry_items
        if not item["is_expired"] and (datetime.fromisoformat(str(item["expiry_date"])) - today).days <= 3
    )
    print(f"\n🔴 Expired: {expired}  |  🟡 Expiring Soon: {expiring}  |  🟢 Fresh: {len(pantry_items) - expired - expiring}")
    print(f"\n🎉 Seeding complete! Total: {len(pantry_items)} items in '{DATABASE_NAME}.pantry_items'")

    client.close()


if __name__ == "__main__":
    seed()
