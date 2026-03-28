"""
Application Configuration
Mealchemy - Pantry Management API
"""

from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ============================================================================
    # APPLICATION METADATA
    # ============================================================================
    APP_NAME: str = "Mealchemy - Pantry Management API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    
    # ============================================================================
    # DATABASE & AUTH
    # ============================================================================
    MONGODB_URL: str = Field(..., description="MongoDB connection string")
    MONGODB_DATABASE: str = "pantry_db"
    
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # ============================================================================
    # CORS CONFIGURATION - Fixed for .env parsing
    # ============================================================================
    # Using Union[str, List[str]] allows Pydantic to read the raw string from .env 
    # without throwing a SettingsError immediately.
    CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def finalize_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Ensures CORS_ORIGINS always ends up as a List[str]."""
        if isinstance(v, str):
            # Clean up potential brackets or quotes if they were accidentally included
            v = v.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # ============================================================================
    # EXTERNAL API INTEGRATIONS
    # ============================================================================
    SPOONACULAR_API_KEY: str = Field(...)
    SPOONACULAR_BASE_URL: str = "https://api.spoonacular.com"
    
    GROQ_API_KEY: str = Field(...)
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    MEAL_PLANNER_PROVIDER: str = "groq" # 'groq' or 'gemini'

    GEMINI_API_KEY_GROCERY: str = Field(...)
    GEMINI_API_KEY_MEAL_PLANNER: str = Field(...)
    GEMINI_MODEL: str = "gemini-2.0-flash" 
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com"
    
    # ============================================================================
    # APP LOGIC SETTINGS
    # ============================================================================
    DEFAULT_MEALS_PER_DAY: int = 1
    DEFAULT_DIET_TYPE: str = "standard"
    DEFAULT_SERVINGS: int = 1
    EXPIRY_WARNING_DAYS: int = 7
    MIN_INGREDIENT_MATCH_PERCENTAGE: int = 50
    RECIPE_CACHE_SIZE: int = 100
    RECIPE_CACHE_TTL: int = 86400

    # ============================================================================
    # PYDANTIC CONFIGURATION
    # ============================================================================
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore", 
    )

    @field_validator("JWT_SECRET_KEY", "SPOONACULAR_API_KEY", "GROQ_API_KEY", 
                     "GEMINI_API_KEY_GROCERY", "GEMINI_API_KEY_MEAL_PLANNER")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("API Key or Secret cannot be empty")
        return v.strip()

# Initialize Singleton
settings = Settings()

def get_settings() -> Settings:
    return settings