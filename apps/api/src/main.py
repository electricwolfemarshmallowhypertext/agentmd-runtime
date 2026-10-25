"""Compatibility entry point for the existing AgentMD API server."""

from .memory.server import app, create_app

__all__ = ["app", "create_app"]
