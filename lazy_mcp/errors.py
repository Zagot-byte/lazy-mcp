"""Exception classes for lazy_mcp."""

from typing import Any


class LazyMCPError(Exception):
    """Base class for all lazy_mcp errors."""


class ToolNotFoundError(LazyMCPError):
    """tool_key not in registry hashmap."""


class ServerOfflineError(LazyMCPError):
    """Server health is DEAD at dispatch time."""


class PartialResultError(LazyMCPError):
    """Stream died mid-response, partial result is attached as self.partial_result."""

    def __init__(self, partial_result: Any, message: str) -> None:
        super().__init__(message)
        self.partial_result = partial_result


class DispatchError(LazyMCPError):
    """Tool call threw an unexpected exception, original exception attached as self.cause."""

    def __init__(self, cause: Exception, tool_key: str) -> None:
        super().__init__(f"Dispatch failed for {tool_key}: {cause}")
        self.cause = cause
        self.tool_key = tool_key


class NoMatchError(LazyMCPError):
    """Matcher found nothing above threshold."""
