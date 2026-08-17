"""
API package for occp.

Exception hierarchy:
    OccpApiClientError (base)
    ├── OccpApiClientCommunicationError (network/timeout)
    └── OccpApiClientAuthenticationError (401/403)

The coordinator maps them onto ConfigEntryAuthFailed and UpdateFailed; nothing else
in the integration imports this package.
"""

from .client import (
    FAN_SPEEDS,
    OccpApiClient,
    OccpApiClientAuthenticationError,
    OccpApiClientCommunicationError,
    OccpApiClientError,
)

__all__ = [
    "FAN_SPEEDS",
    "OccpApiClient",
    "OccpApiClientAuthenticationError",
    "OccpApiClientCommunicationError",
    "OccpApiClientError",
]
