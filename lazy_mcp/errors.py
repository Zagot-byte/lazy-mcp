"""Exception hierarchy for lazy_mcp.

Every exception carries structured context so callers can programmatically
inspect failures without parsing message strings.
"""

from typing import Any


class LazyMCPError(Exception):
    """Base class for all lazy_mcp errors.

    All subclasses guarantee:
      - A human-readable message via str(err)
      - A debug-friendly repr via repr(err)
      - Structured attributes for programmatic access
    """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self})"


class ToolNotFoundError(LazyMCPError):
    """Raised when a tool_key does not exist in the registry.

    Attributes:
        tool_key: The key that was looked up.
        available_keys: Snapshot of registered keys at the time of the error,
                        if provided by the caller. Defaults to None.
    """

    def __init__(
        self,
        tool_key: str,
        available_keys: list[str] | None = None,
    ) -> None:
        self.tool_key = tool_key
        self.available_keys = available_keys

        hint = ""
        if available_keys is not None:
            # Suggest close matches (share a server or tool name component)
            query_parts = set(tool_key.split("::"))
            close = [
                k for k in available_keys
                if query_parts & set(k.split("::"))
            ]
            if close:
                hint = f" Did you mean one of: {', '.join(close)}?"

        super().__init__(
            f"Tool '{tool_key}' is not registered.{hint}"
        )


class ServerOfflineError(LazyMCPError):
    """Raised when dispatching to a server whose health status is DEAD.

    Attributes:
        server_name: The server that is offline.
        fail_count:  Number of consecutive failures recorded, if known.
    """

    def __init__(
        self,
        server_name: str,
        fail_count: int | None = None,
    ) -> None:
        self.server_name = server_name
        self.fail_count = fail_count

        detail = ""
        if fail_count is not None:
            detail = f" ({fail_count} consecutive failures)"

        super().__init__(
            f"Server '{server_name}' is offline{detail}. "
            f"Call registry.reset_health('{server_name}') after reconnecting."
        )


class PartialResultError(LazyMCPError):
    """Raised when a tool stream dies mid-response.

    The partial payload received before the failure is available on
    ``self.partial_result`` so callers can decide whether to retry or
    surface what they have.

    Attributes:
        partial_result: Whatever data was received before the stream broke.
        tool_key:       The tool that was being called, if known.
    """

    def __init__(
        self,
        partial_result: Any,
        message: str,
        tool_key: str | None = None,
    ) -> None:
        self.partial_result = partial_result
        self.tool_key = tool_key

        prefix = f"[{tool_key}] " if tool_key else ""
        has_data = partial_result is not None
        suffix = " Partial data is attached." if has_data else " No data recovered."

        super().__init__(f"{prefix}{message}{suffix}")


class DispatchError(LazyMCPError):
    """Raised when a tool call throws an unexpected exception.

    Wraps the original exception so it isn't lost. Access it via
    ``self.cause`` or use ``raise DispatchError(...) from cause``
    to preserve the full traceback.

    Attributes:
        cause:    The original exception.
        tool_key: The tool that failed.
    """

    def __init__(self, cause: Exception, tool_key: str) -> None:
        self.cause = cause
        self.tool_key = tool_key

        cause_type = type(cause).__name__
        super().__init__(
            f"Dispatch failed for '{tool_key}': "
            f"[{cause_type}] {cause}"
        )

    def __repr__(self) -> str:
        return (
            f"DispatchError(tool_key={self.tool_key!r}, "
            f"cause={self.cause!r})"
        )


class NoMatchError(LazyMCPError):
    """Raised when the matcher finds nothing above the confidence threshold.

    Attributes:
        query:       The intent string that was searched.
        threshold:   The minimum confidence that was required.
        tool_count:  How many tools were searched.
    """

    def __init__(
        self,
        query: str,
        threshold: float | None = None,
        tool_count: int | None = None,
    ) -> None:
        self.query = query
        self.threshold = threshold
        self.tool_count = tool_count

        parts = [f"No tools matched intent: {query!r}"]
        if threshold is not None:
            parts.append(f"threshold={threshold:.2f}")
        if tool_count is not None:
            parts.append(f"searched {tool_count} tool(s)")

        super().__init__(". ".join(parts) + ".")
