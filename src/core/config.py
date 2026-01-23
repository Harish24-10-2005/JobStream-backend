
import os
import platform
import shutil
from typing import Optional, Literal, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, Field, field_validator

def get_default_chrome_path() -> str:
    """Attempts to find the Chrome executable path based on the OS."""
    system = platform.system()
    if system == "Windows":
        paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for path in paths:
            if os.path.exists(path):
                return path
    elif system == "Darwin":  # MacOS
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(path):
            return path
    elif system == "Linux":
        # Look for typical linux paths
        for path in ["/usr/bin/google-chrome", "/usr/bin/chromium-browser"]:
            if os.path.exists(path):
                return path
                
    # Fallback to shutil.which if available in PATH
    path = shutil.which("google-chrome") or shutil.which("chrome")
    return path or ""

def get_default_user_data_dir() -> str:
    """Returns a default user data directory for Chrome."""
    # Use a localized directory within the project or a standard temp location 
    # to avoid conflicts with the user's main Chrome profile.
    # Using a project-local directory is safer for automation.
    return os.path.abspath(os.path.join(os.getcwd(), "chrome_data"))

class Settings(BaseSettings):
    """
    Application Settings managed by Pydantic.
    Reads from environment variables and .env file.
    """
    
    # ============================================
    # Environment & Application Settings
    # ============================================
    environment: Literal["development", "staging", "production"] = Field(
        "development", alias="ENVIRONMENT"
    )
    debug: bool = Field(False, alias="DEBUG")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    
    # ============================================
    # Server Configuration
    # ============================================
    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")
    cors_origins: str = Field(
        "http://localhost:3000,http://127.0.0.1:3000", 
        alias="CORS_ORIGINS"
    )
    
    # ============================================
    # Rate Limiting
    # ============================================
    rate_limit_enabled: bool = Field(True, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(100, alias="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(60, alias="RATE_LIMIT_PERIOD")  # seconds
    
    # ============================================
    # Redis (Production)
    # ============================================
    redis_url: Optional[str] = Field(None, alias="REDIS_URL")
    
    # ============================================
    # Request Limits
    # ============================================
    max_request_size: int = Field(10 * 1024 * 1024, alias="MAX_REQUEST_SIZE")  # 10MB
    
    # AI Models - Groq
    groq_api_key: SecretStr = Field(..., alias="GROQ_API_KEY")
    groq_api_key_fallback: Optional[SecretStr] = Field(None, alias="GROQ_API_KEY1")
    groq_model: str = Field("llama-3.1-8b-instant", alias="GROQ_MODEL")
    
    # AI Models - OpenRouter
    openrouter_api_key: Optional[SecretStr] = Field(None, alias="OPENROUTER_API_KEY2")
    openrouter_api_key_fallback: Optional[SecretStr] = Field(None, alias="OPENROUTER_API_KEY1")
    openrouter_model: str = Field("google/gemma-2-9b-it:free", alias="OPENROUTER_MODEL")
    
    # AI Models - Gemini
    gemini_api_key: Optional[SecretStr] = Field(None, alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-2.0-flash-exp", alias="GEMINI_MODEL1")
    
    # Search
    serpapi_api_key: SecretStr = Field(..., alias="SERPAPI_API_KEY")
    
    # Browser Settings
    headless: bool = Field(True, alias="BROWSER_HEADLESS")
    chrome_path: str = Field(default_factory=get_default_chrome_path)
    user_data_dir: str = Field(default_factory=get_default_user_data_dir)
    profile_directory: str = Field("Default", alias="CHROME_PROFILE_DIR")
    
    # Supabase
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_anon_key: str = Field(..., alias="SUPABASE_ANON_KEY")
    supabase_service_key: Optional[SecretStr] = Field(None, alias="SUPABASE_SERVICE_KEY")
    
    # Encryption (for credentials)
    encryption_key: Optional[SecretStr] = Field(None, alias="ENCRYPTION_KEY")
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    def get_openrouter_key(self) -> str:
        if self.openrouter_api_key:
            return self.openrouter_api_key.get_secret_value()
        raise ValueError("OpenRouter API Key not found.")
        
    def get_openrouter_key1(self) -> str:
        if self.openrouter_api_key_fallback:
            return self.openrouter_api_key_fallback.get_secret_value()
        raise ValueError("OpenRouter API Key not found.")
    
    def get_encryption_key(self) -> bytes:
        """Get or generate encryption key for credential storage."""
        if self.encryption_key:
            key = self.encryption_key.get_secret_value()
            # Ensure key is 32 bytes for AES-256
            return key.encode()[:32].ljust(32, b'\0')
        # Generate a default key from other secrets (not recommended for production)
        import hashlib
        combined = f"{self.groq_api_key.get_secret_value()}"
        return hashlib.sha256(combined.encode()).digest()
    
    # ============================================
    # Production Helper Properties
    # ============================================
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    def get_cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    def get_log_level(self) -> int:
        """Convert log level string to logging constant."""
        import logging
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return levels.get(self.log_level.upper(), logging.INFO)
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid option."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("rate_limit_requests")
    @classmethod
    def validate_rate_limit_requests(cls, v: int) -> int:
        """Validate rate limit requests is positive."""
        if v <= 0:
            raise ValueError("rate_limit_requests must be positive")
        return v
    
    @field_validator("rate_limit_period")
    @classmethod
    def validate_rate_limit_period(cls, v: int) -> int:
        """Validate rate limit period is positive."""
        if v <= 0:
            raise ValueError("rate_limit_period must be positive")
        return v

settings = Settings()
