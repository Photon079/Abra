import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # API Keys & Auth
    NOTION_API_KEY: Optional[str] = None
    # Notion Parent Page or Database IDs
    NOTION_DIARY_DB_ID: Optional[str] = None
    NOTION_TASKS_DB_ID: Optional[str] = None
    NOTION_BRAIN_PAGE_ID: Optional[str] = None  # Parent page ID containing brain/me files
    
    # LLM Keys
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    LLM_PROVIDER: str = "gemini"  # "gemini" or "groq"
    
    # Google API Config
    GOOGLE_CALENDAR_ACCESS_TOKEN: Optional[str] = None
    
    # Server configuration
    PORT: int = 8000
    HOST: str = "127.0.0.1"

    # Directory for local fallback storage if Notion connection is absent
    LOCAL_BRAIN_DIR: str = "/home/anish/Documents/Anish/files"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
