"""
Minimal canary watcher for MVP.

Provides basic health check functionality.
"""

from __future__ import annotations

import time
from typing import Any, Dict


def health_check() -> Dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "codepipeline"
    }


def ping() -> str:
    """Simple ping response."""
    return "pong"


def get_version() -> str:
    """Get version info."""
    return "1.0.0-mvp"


class CanaryWatcher:
    """Simple canary watcher implementation."""
    
    def __init__(self):
        self.start_time = time.time()
        self.checks = 0
    
    def check(self) -> Dict[str, Any]:
        """Perform a canary check."""
        self.checks += 1
        return {
            "status": "ok",
            "uptime": time.time() - self.start_time,
            "checks_performed": self.checks
        }
    
    def status(self) -> str:
        """Get current status."""
        return "running"


# Global instance
watcher = CanaryWatcher()


# Export for compatibility
__all__ = ['health_check', 'ping', 'get_version', 'CanaryWatcher', 'watcher']
