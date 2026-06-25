SHARED CONTEXT (paste above)

Write lazy_mcp/errors.py. No imports except builtins.

Define exactly these exception classes, each with a docstring of one line:

LazyMCPError(Exception)            — base class for all lazy_mcp errors
ToolNotFoundError(LazyMCPError)    — tool_key not in registry hashmap
ServerOfflineError(LazyMCPError)   — server health is DEAD at dispatch time
PartialResultError(LazyMCPError)   — stream died mid-response, partial 
                                     result is attached as self.partial_result
DispatchError(LazyMCPError)        — tool call threw an unexpected exception,
                                     original exception attached as self.cause
NoMatchError(LazyMCPError)         — matcher found nothing above threshold

PartialResultError.__init__(self, partial_result: Any, message: str)
  sets self.partial_result = partial_result

DispatchError.__init__(self, cause: Exception, tool_key: str)
  sets self.cause = cause, self.tool_key = tool_key
