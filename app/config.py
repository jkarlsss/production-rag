"""
Centralized Configuration
Uses pydantic-settings for validated environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
  
  # LLM Configuration
  google_api_key: str
  primary_model: str = "gemini-2.5-flash"
  fallback_model: str = "gemini-3.0-flash-preview"
  
  # LangSmith
  langchain_tracing_v2: bool = True
  langchain_api_key: str = ""
  langsmith_project: str = "Rag Production"
  langsmith_endpoint: str = "https://api.smith.langchain.com"
  
  # Application
  app_env: str = "development"
  log_level: str = "INFO"
  rate_limit: str = "20/minute"
  cache_ttl_seconds: int = 300
  max_retries: int = 3
  
  model_config = {
    "env_file": ".env",
    "extra": "ignore"
  }
  
  @property
  def is_production(self) -> bool:
    return self.app_env == "production"
  
@lru_cache
def get_settings() -> Settings:
  """
  Cache the Settings object.
  Loaded once, reused for subsequent requests.
  Returns the Settings object from the environment variables.
  """
  return Settings()