"""
Application Configuration
Centralized settings management using Pydantic for validation and type safety.
"""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses strict validation (extra='forbid') to catch configuration errors early.
    """
    
    # ============================================================================
    # APPLICATION METADATA
    # ============================================================================
    APP_NAME: str = Field(
        default="Mealchemy - Pantry Management API",
        description="Application display name"
    )
    
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Application version"
    )
    
    DEBUG: bool = Field(
        default=False,
        description="Debug mode - enables verbose logging and error details"
    )
    
    API_V1_PREFIX: str = Field(
        default="/api",
        description="API version 1 route prefix"
    )
    
    # ============================================================================
    # DATABASE CONFIGURATION - MongoDB
    # ============================================================================
    MONGODB_URL: str = Field(
        ...,
        description="MongoDB connection string (e.g., mongodb://localhost:27017)"
    )
    MONGODB_DATABASE: str = Field(
        default="pantry_db",
        description="MongoDB database name"
    )
    
    # ============================================================================
    # AUTHENTICATION & SECURITY
    # ============================================================================
    JWT_SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="Secret key for JWT token signing (min 32 characters)"
    )
    
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        gt=0,
        description="Access token expiration time in minutes"
    )
    
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7,
        gt=0,
        description="Refresh token expiration time in days"
    )
    
    # ============================================================================
    # CORS CONFIGURATION
    # ============================================================================
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins for frontend applications"
    )
    
    # ============================================================================
    # EXTERNAL API INTEGRATIONS
    # ============================================================================
    
    # Spoonacular API - Recipe and Nutrition Data
    SPOONACULAR_API_KEY: str = Field(
        ...,
        description="Spoonacular API key from https://spoonacular.com/food-api"
    )
    
    SPOONACULAR_BASE_URL: str = Field(
        default="https://api.spoonacular.com",
        description="Spoonacular API base URL"
    )
    
    # Groq API - LLM for Meal Planning Intelligence
    GROQ_API_KEY: str = Field(
        ...,
        description="Groq API key from https://console.groq.com"
    )
    
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq LLM model identifier"
    )
    
    GROQ_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Groq API base URL"
    )
    
    # ============================================================================
    # MEAL PLANNING CONFIGURATION
    # ============================================================================
    DEFAULT_MEALS_PER_DAY: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Default number of meals to generate per day"
    )
    
    DEFAULT_DIET_TYPE: str = Field(
        default="standard",
        description="Default diet type (standard, vegetarian, vegan, etc.)"
    )
    
    DEFAULT_SERVINGS: int = Field(
        default=1,
        ge=1,
        le=20,
        description="Default serving size for recipes"
    )
    
    # ============================================================================
    # INGREDIENT & INVENTORY MANAGEMENT
    # ============================================================================
    EXPIRY_WARNING_DAYS: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of days before expiry to trigger warnings"
    )
    
    MIN_INGREDIENT_MATCH_PERCENTAGE: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Minimum % of recipe ingredients that must be in pantry"
    )
    
    # ============================================================================
    # CACHING & PERFORMANCE
    # ============================================================================
    RECIPE_CACHE_SIZE: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum number of recipes to cache in memory"
    )
    
    RECIPE_CACHE_TTL: int = Field(
        default=86400,  # 24 hours
        ge=300,
        le=604800,  # 7 days
        description="Recipe cache time-to-live in seconds"
    )
    
    # ============================================================================
    # PYDANTIC CONFIGURATION
    # ============================================================================
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="forbid",
    )
    
    # ============================================================================
    # FIELD VALIDATORS
    # ============================================================================
    @field_validator("JWT_SECRET_KEY", "SPOONACULAR_API_KEY", "GROQ_API_KEY")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure critical API keys and secrets are not empty."""
        if not v or not v.strip():
            raise ValueError("This field cannot be empty")
        return v.strip()
    
    @field_validator("SPOONACULAR_BASE_URL", "GROQ_BASE_URL")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URLs are properly formatted."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.rstrip("/")
    
    @field_validator("DEFAULT_DIET_TYPE")
    @classmethod
    def validate_diet_type(cls, v: str) -> str:
        """Validate diet type against known options."""
        valid_diets = {
            "standard", "vegetarian", "vegan", "pescatarian",
            "paleo", "keto", "ketogenic", "gluten-free", 
            "gluten free", "dairy-free", "dairy free"
        }
        if v.lower() not in valid_diets:
            raise ValueError(
                f"Diet type must be one of: {', '.join(sorted(valid_diets))}"
            )
        return v.lower()
    
    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        """Ensure JWT algorithm is secure."""
        allowed_algorithms = {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"}
        if v not in allowed_algorithms:
            raise ValueError(
                f"JWT algorithm must be one of: {', '.join(allowed_algorithms)}"
            )
        return v
    
    # ============================================================================
    # COMPUTED PROPERTIES
    # ============================================================================
    @property
    def jwt_access_token_expire_seconds(self) -> int:
        """Get JWT access token expiration in seconds."""
        return self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    @property
    def jwt_refresh_token_expire_seconds(self) -> int:
        """Get JWT refresh token expiration in seconds."""
        return self.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.DEBUG
    
    @property
    def mongodb_connection_string(self) -> str:
        """Get MongoDB connection string (alias for consistency)."""
        return self.MONGODB_URL
    
    # ============================================================================
    # CONFIGURATION HELPERS
    # ============================================================================
    def get_api_config(self) -> dict:
        """
        Get consolidated API configuration for external services.
        
        Returns:
            Dictionary containing all API configurations.
        """
        return {
            "spoonacular": {
                "api_key": self.SPOONACULAR_API_KEY,
                "base_url": self.SPOONACULAR_BASE_URL,
            },
            "groq": {
                "api_key": self.GROQ_API_KEY,
                "model": self.GROQ_MODEL,
                "base_url": self.GROQ_BASE_URL,
            },
        }
    
    def validate_configuration(self) -> dict[str, bool]:
        """
        Validate all critical configuration values are properly set.
        
        Returns:
            Dictionary with validation results for each critical setting.
        """
        return {
            "mongodb": bool(self.MONGODB_URL),
            "jwt_secret": bool(self.JWT_SECRET_KEY and len(self.JWT_SECRET_KEY) >= 32),
            "spoonacular_api": bool(self.SPOONACULAR_API_KEY),
            "groq_api": bool(self.GROQ_API_KEY),
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================
settings = Settings()


# ============================================================================
# DEPENDENCY INJECTION HELPER
# ============================================================================
def get_settings() -> Settings:
    """
    FastAPI dependency for injecting settings into routes.
    
    Usage:
        from fastapi import Depends
        from app.core.settings import get_settings, Settings
        
        @router.get("/config")
        def get_config(settings: Settings = Depends(get_settings)):
            return {"app_name": settings.APP_NAME}
    """
    return settings