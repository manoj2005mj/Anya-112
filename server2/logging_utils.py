"""
Enhanced logging utilities for server2 backend.

Provides structured logging with error tracking, request IDs, and component identification.
"""

import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

# Context variable for request tracking (works across async calls)
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


class ErrorComponent(str, Enum):
    """Components that can be the source of errors"""
    FASTAPI = "fastapi"
    LIVEKIT_AGENT = "livekit_agent"
    LIVEKIT_WORKER = "livekit_worker"
    RAG = "rag"
    TOOL_RACK = "tool_rack"
    TOOL_ALERT = "tool_alert"
    GEMINI_LLM = "gemini_llm"
    GEMINI_IMAGE = "gemini_image"
    EXTERNAL_API = "external_api"
    WEBSOCKET = "websocket"
    DATABASE = "database"
    UNKNOWN = "unknown"


class ErrorSeverity(str, Enum):
    """Severity levels for errors"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class StructuredLogger:
    """
    Enhanced logger that provides structured logging with error tracking.

    Usage:
        logger = get_logger(__name__)
        logger.info("Processing request", request_id="123", endpoint="/chat")
        logger.error("API call failed",
                    component=ErrorComponent.EXTERNAL_API,
                    error=str(e),
                    traceback=traceback.format_exc())
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._name = name

    def _log(
        self,
        level: ErrorSeverity,
        message: str,
        component: Optional[ErrorComponent] = None,
        error: Optional[str] = None,
        traceback_str: Optional[str] = None,
        **context: Any
    ):
        """Internal method to format and log structured messages"""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.value,
            "logger": self._name,
            "message": message,
            "request_id": request_id_var.get(),
            "component": component.value if component else ErrorComponent.UNKNOWN.value,
            **context
        }

        if error:
            log_entry["error"] = error

        if traceback_str:
            log_entry["traceback"] = traceback_str

        # Convert to log format
        log_message = f"{message}"
        if component:
            log_message += f" [{component.value}]"
        if error:
            log_message += f" - {error}"

        # Log with appropriate level
        log_func = getattr(self._logger, level.value)
        log_func(log_message, extra={"structured": log_entry})

    def debug(self, message: str, component: Optional[ErrorComponent] = None, **context):
        """Log debug message"""
        self._log(ErrorSeverity.DEBUG, message, component, **context)

    def info(self, message: str, component: Optional[ErrorComponent] = None, **context):
        """Log info message"""
        self._log(ErrorSeverity.INFO, message, component, **context)

    def warning(self, message: str, component: Optional[ErrorComponent] = None, **context):
        """Log warning message"""
        self._log(ErrorSeverity.WARNING, message, component, **context)

    def error(
        self,
        message: str,
        component: Optional[ErrorComponent] = None,
        error: Optional[str] = None,
        include_traceback: bool = True,
        **context
    ):
        """Log error message with optional traceback"""
        traceback_str = None
        if include_traceback and sys.exc_info()[0] is not None:
            traceback_str = "".join(traceback.format_exception(*sys.exc_info()))

        self._log(
            ErrorSeverity.ERROR,
            message,
            component,
            error=error,
            traceback_str=traceback_str,
            **context
        )

    def critical(
        self,
        message: str,
        component: Optional[ErrorComponent] = None,
        error: Optional[str] = None,
        include_traceback: bool = True,
        **context
    ):
        """Log critical error message with traceback"""
        traceback_str = None
        if include_traceback and sys.exc_info()[0] is not None:
            traceback_str = "".join(traceback.format_exception(*sys.exc_info()))

        self._log(
            ErrorSeverity.CRITICAL,
            message,
            component,
            error=error,
            traceback_str=traceback_str,
            **context
        )


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger for a module"""
    return StructuredLogger(name)


# =============================================================================
# Middleware for Request Tracking
# =============================================================================

class RequestContextMiddleware:
    """
    FastAPI middleware to add request tracking.

    This middleware:
    1. Generates a unique request ID for each incoming request
    2. Stores it in a context variable (accessible across async calls)
    3. Logs incoming requests with source information
    4. Logs responses with timing information
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Generate request ID
            import uuid
            request_id = str(uuid.uuid4())[:8]
            request_id_var.set(request_id)

            # Get request info
            method = scope["method"]
            path = scope["path"]
            query_string = scope.get("query_string", b"").decode()
            client_host = scope.get("client", ("unknown",))[0]

            logger = get_logger("anya.server2.middleware")
            logger.info(
                f"Incoming request: {method} {path}",
                component=ErrorComponent.FASTAPI,
                request_id=request_id,
                method=method,
                path=path,
                query_string=query_string,
                client=client_host
            )

            # Track start time
            import time
            start_time = time.time()

            # Wrap send to log response
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    duration_ms = (time.time() - start_time) * 1000

                    logger.info(
                        f"Response: {status_code}",
                        component=ErrorComponent.FASTAPI,
                        request_id=request_id,
                        status_code=status_code,
                        duration_ms=round(duration_ms, 2)
                    )

                await send(message)

            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


# =============================================================================
# Error Handler
# =============================================================================

async def log_exception_handler(request, exc):
    """
    Global exception handler for FastAPI.
    Logs all exceptions with full context.
    """
    logger = get_logger("anya.server2.exceptions")

    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        component=ErrorComponent.FASTAPI,
        error=str(exc),
        include_traceback=True,
        exception_type=type(exc).__name__,
        request_id=request_id_var.get()
    )

    # Return JSON error response
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={
            "error": type(exc).__name__,
            "message": str(exc),
            "request_id": request_id_var.get()
        }
    )


# =============================================================================
# Utility Functions
# =============================================================================

def log_tool_call(tool_name: str, **context):
    """Log a tool invocation"""
    logger = get_logger("anya.server2.tools")
    logger.info(
        f"Tool called: {tool_name}",
        component=ErrorComponent.TOOL_RACK if "rack" in tool_name else ErrorComponent.TOOL_ALERT,
        tool_name=tool_name,
        **context
    )


def log_llm_call(model: str, prompt_length: int, **context):
    """Log an LLM API call"""
    logger = get_logger("anya.server2.llm")
    logger.info(
        f"LLM call: {model}",
        component=ErrorComponent.GEMINI_LLM,
        model=model,
        prompt_length=prompt_length,
        **context
    )


def log_external_api_call(url: str, method: str, **context):
    """Log an external API call"""
    logger = get_logger("anya.server2.external_api")
    logger.info(
        f"External API call: {method} {url}",
        component=ErrorComponent.EXTERNAL_API,
        url=url,
        method=method,
        **context
    )


def get_error_summary() -> Dict[str, Any]:
    """
    Get a summary of recent errors from the logs.
    Useful for debugging and monitoring.
    """
    # This could be extended to read from a log file or database
    logger = get_logger("anya.server2.monitoring")
    logger.info(
        "Error summary requested",
        component=ErrorComponent.FASTAPI
    )
    return {
        "message": "Error tracking is enabled. Check logs for detailed error information.",
        "log_file": "server2.log",
        "components": [c.value for c in ErrorComponent]
    }
