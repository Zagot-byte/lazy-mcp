SHARED CONTEXT (paste above)

Write pyproject.toml for the lazy-mcp package. No prior content exists.

Use the modern build system — no setup.py, no setup.cfg.

[build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

[project]
  name = "lazy-mcp"
  version = "0.1.0"
  description = "Tool-dispatch middleware for LLM agents. 
                 Keeps tool schemas out of your prompt entirely."
  readme = "README.md"
  license = {text = "MIT"}
  requires-python = ">=3.11"
  dependencies = ["aiohttp>=3.9.0"]

  keywords = [
    "mcp", "llm", "agent", "tools", "middleware", 
    "lazy-loading", "context-window"
  ]

  classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries"
  ]

[project.urls]
  Homepage = "https://github.com/YOUR_HANDLE/lazy-mcp"
  Issues = "https://github.com/YOUR_HANDLE/lazy-mcp"

[project.scripts]
  lazy-mcp = "lazy_mcp.__main__:main"