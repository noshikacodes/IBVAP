"""Common API Dependencies and Injections."""
from typing import Generator
from backend.app.core.config import settings, Settings


def get_settings() -> Settings:
    """Dependency for injecting application settings."""
    return settings
