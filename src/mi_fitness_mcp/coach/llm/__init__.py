"""Optional LLM providers for the coach extension.

Importing this package must not import the Anthropic SDK; the provider module
does that lazily so the base install and MCP stdio startup stay lightweight.
"""
