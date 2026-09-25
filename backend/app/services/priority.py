from typing import Dict, Optional
from backend.app.core.config import settings, DEFAULT_ALERT_PRIORITY_POLICY


def get_alert_severity(event_type: str, custom_policy: Optional[Dict[str, str]] = None) -> str:
    """
    Evaluates and returns the severity level for a given spatial event type
    based on the centralized, configurable alert priority policy.
    
    Defaults:
      - INTRUSION          -> critical
      - TRIPWIRE_CROSSING  -> high
      - LOITERING          -> medium
      - ZONE_EXIT          -> low
    
    Safe fallback for unknown event types is 'medium'.
    """
    policy = custom_policy if custom_policy is not None else settings.ALERT_PRIORITY_POLICY
    clean_type = event_type.strip().lower()
    return policy.get(clean_type, "medium")
