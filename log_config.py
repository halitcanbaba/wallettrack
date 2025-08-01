"""
Logging configuration for WalletTrack
Filters out unnecessary logs and keeps only important information
"""
import logging
import logging.config
import os
import sys
from typing import Dict, Any

# Get log level from environment
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
ENABLE_DEBUG_LOGS = os.getenv('ENABLE_DEBUG_LOGS', 'false').lower() == 'true'

# Set monitor log levels based on debug setting
MONITOR_LOG_LEVEL = 'DEBUG' if ENABLE_DEBUG_LOGS else 'INFO'

# Configure logging levels for different modules
LOGGING_CONFIG: Dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%H:%M:%S"
        },
        "simple": {
            "format": "%(levelname)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "stream": sys.stdout,
            "level": LOG_LEVEL
        }
    },
    "loggers": {
        # Main application loggers
        "app": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        },
        "tron_service": {
            "level": "WARNING",  # Only warnings and errors
            "handlers": ["console"],
            "propagate": False
        },
        "eth_service": {
            "level": "WARNING",  # Only warnings and errors
            "handlers": ["console"],
            "propagate": False
        },
        "tron_monitor": {
            "level": MONITOR_LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False
        },
        "eth_monitor": {
            "level": MONITOR_LOG_LEVEL,
            "handlers": ["console"],
            "propagate": False
        },
        # Third-party loggers
        "httpx": {
            "level": "WARNING",  # Hide HTTP request logs
            "handlers": ["console"],
            "propagate": False
        },
        "uvicorn": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False
        },
        "uvicorn.access": {
            "level": "WARNING",  # Hide access logs
            "handlers": ["console"],
            "propagate": False
        },
        "websocket_manager": {
            "level": "WARNING",  # Hide WebSocket connection logs
            "handlers": ["console"],
            "propagate": False
        },
        # Orderbook service loggers
        "app.services.binance_service": {
            "level": "WARNING",  # Only warnings and errors
            "handlers": ["console"],
            "propagate": False
        },
        "app.services.whitebit_service": {
            "level": "WARNING",  # Only warnings and errors
            "handlers": ["console"],
            "propagate": False
        },
        "app.services.cointr_service": {
            "level": "WARNING",  # Only warnings and errors
            "handlers": ["console"],
            "propagate": False
        },
        "app.api.orderbook": {
            "level": "WARNING",  # Only warnings and errors
            "handlers": ["console"],
            "propagate": False
        },
        "app.services.transaction_service": {
            "level": "WARNING",  # Only warnings and errors
            "handlers": ["console"],
            "propagate": False
        },
        "app.api.transactions": {
            "level": "WARNING",  # Only warnings and errors
            "handlers": ["console"],
            "propagate": False
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"]
    }
}

def setup_logging():
    """Setup logging configuration"""
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Suppress specific noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("websocket_manager").setLevel(logging.WARNING)
    
    # Set rate limiting logs to WARNING
    logging.getLogger("tron_service").setLevel(logging.WARNING)
    logging.getLogger("eth_service").setLevel(logging.WARNING)
    
    # Set orderbook services to WARNING level
    logging.getLogger("app.services.binance_service").setLevel(logging.WARNING)
    logging.getLogger("app.services.whitebit_service").setLevel(logging.WARNING)
    logging.getLogger("app.services.cointr_service").setLevel(logging.WARNING)
    logging.getLogger("app.api.orderbook").setLevel(logging.WARNING)
    
    # Set transaction services to WARNING level 
    logging.getLogger("app.services.transaction_service").setLevel(logging.WARNING)
    logging.getLogger("app.api.transactions").setLevel(logging.WARNING)
    
    print("🔧 Logging configuration applied - Reduced verbosity")

if __name__ == "__main__":
    setup_logging()
