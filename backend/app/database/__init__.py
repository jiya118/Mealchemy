"""
PantryMind — MongoDB Atlas Database Connection Module

This module provides a shared MongoDB client and database reference
that can be imported anywhere in the project.

Usage:
    from backend.app.database import db, pantry_items_collection
"""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file (project root)
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "pantrymind")

# Create MongoDB client and database reference
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

# ─── Collection References ────────────────────────────────────────
pantry_items_collection = db["pantry_items"]
