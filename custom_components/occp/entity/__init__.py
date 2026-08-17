"""
Entity package for occp.

Architecture:
    All platform entities inherit from (PlatformEntity, OccpEntity).
    MRO order matters — platform-specific class first, then the integration base.
    Entities read data from coordinator.data and NEVER call the API client directly.
    Unique IDs follow the pattern: {entry_id}_{description.key}

See entity/base.py for the OccpEntity base class.
"""

from .base import OccpEntity

__all__ = ["OccpEntity"]
