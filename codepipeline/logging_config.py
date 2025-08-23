"""
Minimal logging configuration for MVP.

Provides basic structured logging functionality.
"""

from __future__ import annotations

import logging
import sys


def get_logger(name: str = __name__) -> logging.Logger:
    """Get a configured logger instance."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Basic console handler
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger


def configure_logging(level: str = "INFO") -> None:
    """Configure basic logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


class StructuredLogger:
    """Simple structured logger for MVP."""
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with structured data."""
        if kwargs:
            self.logger.info(f"{message} - {kwargs}")
        else:
            self.logger.info(message)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with structured data."""
        if kwargs:
            self.logger.error(f"{message} - {kwargs}")
        else:
            self.logger.error(message)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with structured data."""
        if kwargs:
            self.logger.warning(f"{message} - {kwargs}")
        else:
            self.logger.warning(message)


# Global logger instance
logger = get_logger(__name__)


# Export for compatibility
__all__ = ['get_logger', 'configure_logging', 'StructuredLogger', 'logger']
